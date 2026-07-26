"""
carrier_recovery.py — "which carriers came back after the disruption, and which did not".

Lifted out of the /insights/carrier-recovery endpoint so it is callable from more than HTTP:
AI search answers the same question ("איזה חברות עוד לא חזרו לטוס לישראל?") and must produce the
SAME numbers as the /recovery page, which only happens if there is one implementation. The
endpoint is now a thin wrapper over compute_carrier_recovery().

The SQL lives here; the classification rules stay in insights_logic as plain functions (testable
without a PostgreSQL dialect behind them).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.flight_status import CANCELLED_SQL, NOT_CANCELLED_SQL
from app.services.insights_logic import classify_recovery, detect_crisis_window, find_return_date

# A carrier needs this many operated departures across the baseline period before it appears on
# the recovery page. Without it a carrier with 2 lifetime flights that flew both last month shows
# up as "486% recovered", which is noise presented as a finding.
MIN_BASELINE_FLIGHTS = 60


def _months_between(start_iso: str, end_iso: str) -> float:
    """Whole months between two 'YYYY-MM-01' strings, used to turn a baseline total into a rate."""
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end.year - start.year) * 12 + (end.month - start.month)


def compute_carrier_recovery(db: Session, min_baseline_flights: int = MIN_BASELINE_FLIGHTS) -> dict:
    """
    Each carrier's current schedule as a percentage of its own pre-disruption monthly average,
    bucketed into never_returned / partial / recovered / expanded.

    Recomputes on every call, so a carrier resuming next month appears without a code change.

    Baseline is each carrier's own pre-disruption average, not a global figure: a carrier that ran
    3 flights a week before and runs 3 a week now has fully recovered, and comparing it against
    El Al's volume would bury that.
    """
    # 1. Find the disruption window from the data, so the baseline period ends where the
    #    disruption starts rather than at a hardcoded date.
    monthly = db.execute(
        text(f"""
            SELECT
                to_char(date_trunc('month', scheduled_time), 'YYYY-MM') AS month,
                COUNT(*) AS scheduled,
                SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) AS cancelled
            FROM flights
            WHERE direction = 'D' AND scheduled_time IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
    ).fetchall()

    if not monthly:
        return {"carriers": [], "crisis_window": None, "summary": {}}

    window = detect_crisis_window(
        [{"month": r.month, "scheduled": int(r.scheduled or 0), "cancelled": int(r.cancelled or 0)}
         for r in monthly]
    )
    if not window:
        # No disruption in this data — there is no recovery story to tell, and inventing a
        # cutoff would produce confident-looking noise.
        return {"carriers": [], "crisis_window": None, "summary": {}}

    baseline_end = f"{window['start']}-01"
    data_start = f"{monthly[0].month}-01"

    # 2. Per-carrier baseline volume and current volume.
    carriers = db.execute(
        text(f"""
            WITH baseline AS (
                SELECT airline_code,
                       MAX(airline_name) AS airline_name,
                       COUNT(*) AS baseline_flights
                FROM flights
                WHERE direction = 'D' AND {NOT_CANCELLED_SQL}
                  AND scheduled_time >= CAST(:data_start AS timestamptz)
                  AND scheduled_time <  CAST(:baseline_end AS timestamptz)
                GROUP BY airline_code
                HAVING COUNT(*) >= :min_baseline
            ),
            recent AS (
                SELECT airline_code, COUNT(*) AS last30_flights
                FROM flights
                WHERE direction = 'D' AND {NOT_CANCELLED_SQL}
                  AND scheduled_time >= CURRENT_TIMESTAMP - INTERVAL '30 days'
                  AND scheduled_time <  CURRENT_TIMESTAMP
                GROUP BY airline_code
            )
            SELECT b.airline_code, b.airline_name, b.baseline_flights,
                   COALESCE(r.last30_flights, 0) AS last30_flights
            FROM baseline b
            LEFT JOIN recent r ON r.airline_code = b.airline_code
        """),
        {"data_start": data_start, "baseline_end": baseline_end, "min_baseline": min_baseline_flights},
    ).fetchall()

    if not carriers:
        return {"carriers": [], "crisis_window": window, "summary": {}}

    codes = [c.airline_code for c in carriers]

    # 3. Operating days per carrier, for gap-based return detection. Only qualifying carriers,
    #    and only from the baseline period onward, so this stays a few thousand rows.
    day_rows = db.execute(
        text(f"""
            SELECT airline_code, CAST(scheduled_time AS date) AS day
            FROM flights
            WHERE direction = 'D' AND {NOT_CANCELLED_SQL}
              AND airline_code = ANY(:codes)
              AND scheduled_time >= CAST(:data_start AS timestamptz)
              AND scheduled_time < CURRENT_TIMESTAMP
            GROUP BY airline_code, CAST(scheduled_time AS date)
        """),
        {"codes": codes, "data_start": data_start},
    ).fetchall()

    days_by_carrier: dict[str, list[date]] = {}
    for row in day_rows:
        days_by_carrier.setdefault(row.airline_code, []).append(row.day)

    baseline_months = max(1.0, _months_between(data_start, baseline_end))
    # Only resumptions from the disruption onward count as returns; a charter operator's
    # ordinary off-season gap months earlier is not a return from this disruption.
    crisis_start = date.fromisoformat(baseline_end)

    results = [
        classify_recovery({
            "airline_code": c.airline_code,
            "airline_name": c.airline_name,
            "baseline_flights": int(c.baseline_flights or 0),
            "baseline_months": baseline_months,
            "last30_flights": int(c.last30_flights or 0),
            "return_date": find_return_date(
                days_by_carrier.get(c.airline_code, []), not_before=crisis_start
            ),
        })
        for c in carriers
    ]
    results.sort(key=lambda r: (r["recovery_pct"] is None, r["recovery_pct"] or 0))

    summary: dict[str, int] = {}
    for r in results:
        summary[r["bucket"]] = summary.get(r["bucket"], 0) + 1

    return {
        "carriers": results,
        "crisis_window": window,
        "summary": summary,
        "baseline_period": {"start": data_start, "end": baseline_end, "months": round(baseline_months, 1)},
        "min_baseline_flights": min_baseline_flights,
    }
