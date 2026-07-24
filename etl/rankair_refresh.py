"""
rankair_refresh.py

Refreshes the destination_airline_metrics aggregate table for RankAir.
Runs an atomic UPSERT for the current 30-day rolling window.

Designed to be called every 15 minutes alongside the main ETL pipeline.
"""

import logging

from etl.config import get_config
from etl.load import get_pg_connection

logger = logging.getLogger(__name__)

# Cancellation detection — mirrors backend/app/services/flight_status.py. Kept in sync BY HAND: the
# etl package deploys separately and cannot import the backend app. '%cancel%' matches
# CANCELED/CANCELLED/canceled/cancelled, so an upstream English spelling/casing change can't silently
# stop counting cancellations (status_he '%בוטל%' is a redundant safety net). Cancelled flights are
# excluded from every delay-derived metric because their delay_minutes is junk (values up to ±2700).
_CANCELLED_SQL = "(status_en ILIKE '%cancel%' OR status_he ILIKE '%בוטל%')"
_NOT_CANCELLED_SQL = f"NOT {_CANCELLED_SQL}"

# ---------------------------------------------------------------------------
# Destination normalization
#
# Maps raw location_city_en value (as stored in the DB) to a tuple of
# (normalized_en, normalized_he).
#
# Python owns the mapping; SQL applies it via a generated CASE expression.
# Add entries here to extend normalization without touching the SQL logic.
# ---------------------------------------------------------------------------
DESTINATION_NORMALIZATION: dict[str, tuple[str, str]] = {
    "LONDON LUTON":    ("LONDON", "לונדון"),
    "LONDON HEATHROW": ("LONDON", "לונדון"),
    "LONDON GATWICK":  ("LONDON", "לונדון"),
}


# ---------------------------------------------------------------------------
# CASE expression builders
# ---------------------------------------------------------------------------

def _case_en(mapping: dict[str, tuple[str, str]]) -> str:
    """Return a SQL CASE expression normalizing location_city_en."""
    if not mapping:
        return "location_city_en"
    branches = "\n            ".join(
        f"WHEN location_city_en = '{raw}' THEN '{norm_en}'"
        for raw, (norm_en, _) in mapping.items()
    )
    return f"CASE {branches} ELSE location_city_en END"


def _case_he(mapping: dict[str, tuple[str, str]]) -> str:
    """Return a SQL CASE expression normalizing location_he (keyed on location_city_en)."""
    if not mapping:
        return "location_he"
    branches = "\n            ".join(
        f"WHEN location_city_en = '{raw}' THEN '{norm_he}'"
        for raw, (_, norm_he) in mapping.items()
    )
    return f"CASE {branches} ELSE location_he END"


# ---------------------------------------------------------------------------
# SQL builder
# ---------------------------------------------------------------------------

def _build_refresh_sql(mapping: dict[str, tuple[str, str]]) -> str:
    """
    Build the full UPSERT SQL.

    A CTE applies destination normalization once so the CASE expressions
    do not repeat in SELECT and GROUP BY. All aggregation stays in SQL.
    """
    return f"""
WITH normalized AS (
    SELECT
        {_case_en(mapping)} AS destination_city_en,
        {_case_he(mapping)} AS destination_city_he,
        airline_name,
        delay_minutes,
        status_en,
        status_he
    FROM flights
    WHERE direction = 'D'
      AND scheduled_time >= NOW() - INTERVAL '30 days'
)
INSERT INTO destination_airline_metrics (
    destination_city_en,
    destination_city_he,
    airline_name,
    window_type,
    total_flights,
    on_time_pct,
    cancel_pct,
    severe_delay_pct,
    avg_delay_positive,
    p95_delay
)
SELECT
    destination_city_en,
    destination_city_he,
    airline_name,
    '30d'                                                                              AS window_type,

    -- cancel_pct counts cancellations; every other metric excludes them (denominator stays
    -- COUNT(*) so cancellations correctly lower on_time_pct). See _CANCELLED_SQL above.
    COUNT(*)                                                                           AS total_flights,
    100.0 * SUM(CASE WHEN {_NOT_CANCELLED_SQL} AND delay_minutes <= 15 THEN 1 ELSE 0 END) / COUNT(*) AS on_time_pct,
    100.0 * SUM(CASE WHEN {_CANCELLED_SQL} THEN 1 ELSE 0 END) / COUNT(*)              AS cancel_pct,
    100.0 * SUM(CASE WHEN {_NOT_CANCELLED_SQL} AND delay_minutes > 60 THEN 1 ELSE 0 END) / COUNT(*) AS severe_delay_pct,
    AVG(CASE WHEN {_NOT_CANCELLED_SQL} AND delay_minutes > 0 THEN delay_minutes END)  AS avg_delay_positive,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_minutes)
        FILTER (WHERE {_NOT_CANCELLED_SQL} AND delay_minutes > 0)                     AS p95_delay

FROM normalized
GROUP BY destination_city_en, destination_city_he, airline_name
HAVING COUNT(*) >= 10

ON CONFLICT (destination_city_en, airline_name, window_type)
DO UPDATE SET
    destination_city_he  = EXCLUDED.destination_city_he,
    total_flights        = EXCLUDED.total_flights,
    on_time_pct          = EXCLUDED.on_time_pct,
    cancel_pct           = EXCLUDED.cancel_pct,
    severe_delay_pct     = EXCLUDED.severe_delay_pct,
    avg_delay_positive   = EXCLUDED.avg_delay_positive,
    p95_delay            = EXCLUDED.p95_delay,
    updated_at           = NOW();
"""


# ---------------------------------------------------------------------------
# Refresh logic
# ---------------------------------------------------------------------------

def refresh(conn) -> None:
    """Execute one refresh cycle inside a single transaction."""
    sql = _build_refresh_sql(DESTINATION_NORMALIZATION)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        logger.info("destination_airline_metrics refreshed — %d rows affected", cur.rowcount)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def run(cfg: dict) -> None:
    conn = get_pg_connection(cfg)
    try:
        refresh(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run(get_config())
