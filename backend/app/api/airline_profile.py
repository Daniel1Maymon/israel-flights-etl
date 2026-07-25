"""
Airline profile endpoints — the data behind the /airlines page.

The page is airline-first: pick one carrier, see its overall record and its record on every route
it flies. That is the mirror of the front page, which is destination-first.

Metric definitions are imported, never re-declared. `flight_status.py` owns "is this cancelled?"
and the on-time threshold matches the destination performance table and the top-on-time
leaderboard (delay <= 15 minutes, early counts as on time). A page that disagreed with the front
page about the same airline on the same route would be worse than no page.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.carrier_nationality import ISRAELI_CARRIER_SQL
from app.services.flight_status import CANCELLED_SQL, NOT_CANCELLED_SQL

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/airlines", tags=["airline-profile"])

ON_TIME_THRESHOLD_MIN = 15

# The site's canonical destination grouping, copied in behaviour from /destinations/cities:
# group by the first Hebrew word of location_he so all London-area airports collapse into one
# LONDON / לונדון row, falling back to location_city_en when there is no Hebrew name.
# Using anything else here would make this page report a different destination count than the
# search box on the front page — and, in the endpoint this replaces, a different count in Hebrew
# than in English.
DESTINATION_GROUP_SQL = """
    CASE
        WHEN location_he IS NOT NULL AND TRIM(location_he) != ''
            THEN SPLIT_PART(TRIM(location_he), ' ', 1)
        ELSE location_city_en
    END
"""


def _pct(numerator, denominator) -> float:
    return round(100.0 * (numerator or 0) / denominator, 2) if denominator else 0.0


@router.get(
    "/directory",
    summary="Airlines available for the profile page",
    description="Code, name and departure volume for every carrier, for the airline picker.",
)
async def airline_directory(
    q: Optional[str] = Query(None, description="Substring match on airline name or code"),
    min_flights: int = Query(
        1, ge=1,
        description="Hide carriers below this many departures; the default keeps everything",
    ),
    db: Session = Depends(get_db),
):
    """
    Feeds the search box. Ordered by volume so the carriers most people are looking for surface
    first when the query is empty.
    """
    try:
        pattern = f"%{q.strip()}%" if q and q.strip() else "%"
        rows = db.execute(
            text(f"""
                SELECT
                    airline_code,
                    MAX(airline_name) AS airline_name,
                    COUNT(*) AS total_flights,
                    BOOL_OR({ISRAELI_CARRIER_SQL}) AS is_israeli
                FROM flights
                WHERE direction = 'D'
                  AND airline_code IS NOT NULL AND TRIM(airline_code) != ''
                  AND airline_name IS NOT NULL AND TRIM(airline_name) != ''
                  AND (airline_name ILIKE :pattern OR airline_code ILIKE :pattern)
                GROUP BY airline_code
                HAVING COUNT(*) >= :min_flights
                ORDER BY COUNT(*) DESC
            """),
            {"pattern": pattern, "min_flights": min_flights},
        ).fetchall()

        return {
            "airlines": [
                {
                    "airline_code": r.airline_code,
                    "airline_name": r.airline_name,
                    "total_flights": int(r.total_flights or 0),
                    "is_israeli": bool(r.is_israeli),
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error("Error retrieving airline directory", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve airline directory")


@router.get(
    "/{airline_code}/profile",
    summary="One airline's overall performance, with airport benchmark",
    description=(
        "Headline KPIs, delay distribution and monthly on-time trend for a single carrier, "
        "alongside the same figures for the whole airport as context."
    ),
)
async def airline_profile(airline_code: str, db: Session = Depends(get_db)):
    """
    Everything above the per-route table.

    The airport-wide figures are returned in the same response rather than fetched separately, so
    the tiles can never render a carrier's number next to a stale benchmark.
    """
    code = airline_code.strip().upper()
    try:
        carrier = db.execute(
            text(f"""
                SELECT
                    COUNT(*) AS scheduled,
                    SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) AS cancelled,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes <= :threshold THEN 1 ELSE 0 END) AS on_time,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes IS NOT NULL THEN 1 ELSE 0 END) AS measured,
                    AVG(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes > 0 THEN delay_minutes END) AS avg_delay_when_late,
                    MAX(CASE WHEN {NOT_CANCELLED_SQL} THEN delay_minutes END) AS worst_delay,
                    COUNT(DISTINCT {DESTINATION_GROUP_SQL}) AS destinations
                FROM flights
                WHERE direction = 'D' AND airline_code = :code
            """),
            {"code": code, "threshold": ON_TIME_THRESHOLD_MIN},
        ).fetchone()

        if not carrier or not carrier.scheduled:
            raise HTTPException(status_code=404, detail=f"No departures found for airline {code}")

        # No airport-wide benchmark is returned. This page compares a carrier to ITSELF — its
        # routes against its own average, its months against its own record. Dropping in a
        # cross-carrier figure would quietly turn it back into a ranking page.

        name_row = db.execute(
            text("""
                SELECT MAX(airline_name) AS airline_name,
                       BOOL_OR(%s) AS is_israeli
                FROM flights WHERE airline_code = :code
            """ % ISRAELI_CARRIER_SQL),
            {"code": code},
        ).fetchone()

        def kpis(row) -> dict:
            scheduled = int(row.scheduled or 0)
            # On-time is expressed against flights that actually operated AND have a delay
            # reading. Dividing by everything scheduled would let a carrier's cancellations drag
            # its punctuality down, double-counting the cancellation it already reports.
            measured = int(row.measured or 0)
            return {
                "scheduled": scheduled,
                "cancelled": int(row.cancelled or 0),
                "cancelled_pct": _pct(row.cancelled, scheduled),
                "on_time_pct": _pct(row.on_time, measured),
                "avg_delay_when_late": round(float(row.avg_delay_when_late), 1)
                if row.avg_delay_when_late is not None else None,
                "worst_delay": int(row.worst_delay) if row.worst_delay is not None else None,
                "destinations": int(row.destinations or 0),
            }

        # The single flight behind the worst-delay figure.
        #
        # `worst_delay` is a MAX, so it is set by one departure out of thousands — for Arkia it is
        # 2,883 minutes, ten times that carrier's 99th percentile, and the flight in question was
        # held two days during the March-April disruption and recorded as DEPARTED rather than
        # CANCELED. Presented bare, the tile reads as a property of the airline. Naming the flight
        # turns it back into what it is: a fact about one departure the reader can weigh.
        worst_flight = db.execute(
            text(f"""
                SELECT flight_number, location_city_en, location_he, scheduled_time, delay_minutes
                FROM flights
                WHERE direction = 'D' AND airline_code = :code
                  AND {NOT_CANCELLED_SQL} AND delay_minutes IS NOT NULL
                ORDER BY delay_minutes DESC
                LIMIT 1
            """),
            {"code": code},
        ).fetchone()

        # Delay distribution — the shape of a carrier's lateness, not just its on-time share.
        buckets = db.execute(
            text(f"""
                SELECT
                    SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) AS cancelled,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes < 0 THEN 1 ELSE 0 END) AS early,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes BETWEEN 0 AND 15 THEN 1 ELSE 0 END) AS on_time,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes > 15 AND delay_minutes <= 60 THEN 1 ELSE 0 END) AS late,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes > 60 THEN 1 ELSE 0 END) AS very_late
                FROM flights
                WHERE direction = 'D' AND airline_code = :code
            """),
            {"code": code},
        ).fetchone()

        # Monthly trend, so the carrier's own disruption dip is visible.
        trend_rows = db.execute(
            text(f"""
                SELECT
                    to_char(date_trunc('month', scheduled_time), 'YYYY-MM') AS month,
                    COUNT(*) AS scheduled,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes IS NOT NULL THEN 1 ELSE 0 END) AS measured,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes <= :threshold THEN 1 ELSE 0 END) AS on_time,
                    SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) AS cancelled
                FROM flights
                WHERE direction = 'D' AND airline_code = :code AND scheduled_time IS NOT NULL
                GROUP BY 1 ORDER BY 1
            """),
            {"code": code, "threshold": ON_TIME_THRESHOLD_MIN},
        ).fetchall()

        return {
            "airline_code": code,
            "airline_name": name_row.airline_name if name_row else code,
            "is_israeli": bool(name_row.is_israeli) if name_row else False,
            "carrier": kpis(carrier),
            "worst_delay_flight": {
                "flight_number": worst_flight.flight_number,
                "city_en": worst_flight.location_city_en,
                "city_he": worst_flight.location_he,
                "scheduled_time": worst_flight.scheduled_time.isoformat()
                if worst_flight.scheduled_time else None,
                "delay_minutes": int(worst_flight.delay_minutes),
            } if worst_flight else None,
            "delay_distribution": {
                "early": int(buckets.early or 0),
                "on_time": int(buckets.on_time or 0),
                "late": int(buckets.late or 0),
                "very_late": int(buckets.very_late or 0),
                "cancelled": int(buckets.cancelled or 0),
            },
            "monthly": [
                {
                    "month": r.month,
                    "scheduled": int(r.scheduled or 0),
                    # Flights the percentage is actually computed from. Exposed because a month
                    # where a carrier cancelled almost everything yields a tiny sample that can
                    # read as a perfect record: Delta shows 100% on-time in 2026-03 off a dozen
                    # operated flights. The client needs this to refuse to plot such a month.
                    "measured": int(r.measured or 0),
                    "on_time_pct": _pct(r.on_time, int(r.measured or 0)),
                    "cancelled_pct": _pct(r.cancelled, int(r.scheduled or 0)),
                }
                for r in trend_rows
            ],
            "on_time_threshold_minutes": ON_TIME_THRESHOLD_MIN,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving airline profile", airline=code, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve airline profile")


@router.get(
    "/{airline_code}/routes",
    summary="One airline's performance on every destination it serves",
    description=(
        "Per-destination departure performance for a single carrier, using the site's canonical "
        "cancellation definition, on-time threshold and destination grouping."
    ),
)
async def airline_routes(
    airline_code: str,
    min_flights: int = Query(
        1, ge=1,
        description="Minimum departures on a route for it to be listed",
    ),
    db: Session = Depends(get_db),
):
    """
    The centrepiece of the page.

    Replaces `/{airline_code}/destinations`, which used a 20-minute on-time window, matched
    cancellations with a bare `status_en == 'CANCELED'` instead of the canonical helper, and
    grouped by country in Hebrew but by city in English. Those made the same route report
    different numbers here than on the front page, and different numbers in each language.
    """
    code = airline_code.strip().upper()
    try:
        rows = db.execute(
            text(f"""
                SELECT
                    MIN(location_city_en) AS city_en,
                    -- Group by the first Hebrew word (canonical), but LABEL with the shortest
                    -- full Hebrew name in the group. Using the group key as the label truncates
                    -- multi-word cities — 'אבו דאבי' displayed as 'אבו' — while the shortest full
                    -- name still collapses London's airports to a bare 'לונדון'.
                    (ARRAY_AGG(TRIM(location_he) ORDER BY LENGTH(TRIM(location_he)))
                        FILTER (WHERE location_he IS NOT NULL AND TRIM(location_he) != ''))[1] AS city_he,
                    MIN(country_en) AS country_en,
                    COUNT(*) AS scheduled,
                    SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) AS cancelled,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes IS NOT NULL THEN 1 ELSE 0 END) AS measured,
                    SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes <= :threshold THEN 1 ELSE 0 END) AS on_time,
                    AVG(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes > 0 THEN delay_minutes END) AS avg_delay_when_late
                FROM flights
                WHERE direction = 'D'
                  AND airline_code = :code
                  AND location_city_en IS NOT NULL AND location_city_en != ''
                GROUP BY {DESTINATION_GROUP_SQL}
                HAVING COUNT(*) >= :min_flights
                ORDER BY COUNT(*) DESC
            """),
            {"code": code, "threshold": ON_TIME_THRESHOLD_MIN, "min_flights": min_flights},
        ).fetchall()

        routes = [
            {
                "city_en": r.city_en,
                "city_he": r.city_he,
                "country_en": r.country_en,
                "total_flights": int(r.scheduled or 0),
                "on_time_pct": _pct(r.on_time, int(r.measured or 0)),
                "cancelled_pct": _pct(r.cancelled, int(r.scheduled or 0)),
                "avg_delay_minutes_positive_only": round(float(r.avg_delay_when_late), 1)
                if r.avg_delay_when_late is not None else None,
            }
            for r in rows
            if r.city_en
        ]

        return {
            "airline_code": code,
            "routes": routes,
            "total_routes": len(routes),
            "on_time_threshold_minutes": ON_TIME_THRESHOLD_MIN,
        }

    except Exception as e:
        logger.error("Error retrieving airline routes", airline=code, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve airline routes")
