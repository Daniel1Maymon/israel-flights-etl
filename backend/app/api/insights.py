"""
Insights endpoints — the aggregates behind the /insights and /recovery pages.

Every query here is read-only aggregation over `flights`. The SQL does the grouping; the
classification rules live in `app.services.insights_logic` as plain functions so they can be
tested without a PostgreSQL dialect behind them (the test DB is SQLite).

Cancellation detection always comes from `flight_status.py` and carrier nationality always from
`carrier_nationality.py`. Neither is re-implemented here.
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.carrier_nationality import ISRAELI_CARRIER_SQL
from app.services.flight_status import CANCELLED_SQL, NOT_CANCELLED_SQL
from app.services.insights_logic import (
    classify_recovery,
    detect_crisis_window,
    find_return_date,
    month_range,
    zero_fill,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

# On-time is delay <= 15 minutes, matching the definition already used by the destination
# performance table and the top-on-time leaderboard. Changing it here alone would make the
# insights page disagree with the front page about the same airline.
ON_TIME_THRESHOLD_MIN = 15

# A carrier needs this many operated departures across the baseline period before it appears on
# the recovery page. Without it a carrier with 2 lifetime flights that flew both last month shows
# up as "486% recovered", which is noise presented as a finding.
MIN_BASELINE_FLIGHTS = 60


def _pct(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 2) if denominator else 0.0


@router.get(
    "/monthly-by-nationality",
    summary="Monthly departures and cancellations, Israeli vs foreign carriers",
    description=(
        "Per-month scheduled/cancelled departure counts split by carrier nationality, plus the "
        "disruption window derived from the data rather than hardcoded."
    ),
)
async def monthly_by_nationality(db: Session = Depends(get_db)):
    """
    Feeds the 'when the sky closed' and 'blue-and-white share' story cards.

    Returns one flat row per month (Recharts reads flat rows directly) covering EVERY month in the
    data range, including months where a nationality has no flights at all — April 2026 had 318
    foreign departures against 4,891 in February, and a missing bar reads as a broken chart rather
    than as the story.
    """
    try:
        rows = db.execute(
            text(f"""
                SELECT
                    to_char(date_trunc('month', scheduled_time), 'YYYY-MM') AS month,
                    CASE WHEN {ISRAELI_CARRIER_SQL} THEN 'israeli' ELSE 'foreign' END AS nationality,
                    COUNT(*) AS scheduled,
                    SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) AS cancelled
                FROM flights
                WHERE direction = 'D' AND scheduled_time IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1, 2
            """)
        ).fetchall()

        if not rows:
            return {"months": [], "crisis_window": None}

        by_month: dict[str, dict[str, dict[str, int]]] = {}
        for row in rows:
            slot = by_month.setdefault(row.month, {})
            slot[row.nationality] = {
                "scheduled": int(row.scheduled or 0),
                "cancelled": int(row.cancelled or 0),
            }

        all_months = month_range(min(by_month), max(by_month))
        empty = {"scheduled": 0, "cancelled": 0}

        months = []
        for month in all_months:
            slot = by_month.get(month, {})
            il = slot.get("israeli", empty)
            fo = slot.get("foreign", empty)
            total_scheduled = il["scheduled"] + fo["scheduled"]
            total_cancelled = il["cancelled"] + fo["cancelled"]
            months.append({
                "month": month,
                "israeli_scheduled": il["scheduled"],
                "israeli_cancelled": il["cancelled"],
                "israeli_operated": il["scheduled"] - il["cancelled"],
                "israeli_cancelled_pct": _pct(il["cancelled"], il["scheduled"]),
                "foreign_scheduled": fo["scheduled"],
                "foreign_cancelled": fo["cancelled"],
                "foreign_operated": fo["scheduled"] - fo["cancelled"],
                "foreign_cancelled_pct": _pct(fo["cancelled"], fo["scheduled"]),
                "total_scheduled": total_scheduled,
                "total_cancelled": total_cancelled,
                "total_cancelled_pct": _pct(total_cancelled, total_scheduled),
                # Share of the month's schedule flown by Israeli carriers — the 35% -> 47% shift.
                "israeli_share_pct": _pct(il["scheduled"], total_scheduled),
            })

        crisis_window = detect_crisis_window(
            [{"month": m["month"], "scheduled": m["total_scheduled"], "cancelled": m["total_cancelled"]}
             for m in months]
        )

        return {"months": months, "crisis_window": crisis_window}

    except Exception as e:
        logger.error("Error retrieving monthly-by-nationality insights", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve monthly insights")


@router.get(
    "/by-weekday",
    summary="On-time performance by day of week",
    description="Departure punctuality per weekday. Cancelled flights are excluded.",
)
async def by_weekday(db: Session = Depends(get_db)):
    """
    Feeds the 'Saturday is the best day to fly' card.

    Cancelled flights are excluded outright: a cancellation is not a slow departure, and counting
    it as one would let a month of cancellations masquerade as a punctuality collapse.
    Weekday indices follow PostgreSQL's DOW, where 0 = Sunday.
    """
    try:
        rows = db.execute(
            text(f"""
                SELECT
                    EXTRACT(dow FROM scheduled_time)::int AS dow,
                    COUNT(*) AS flights,
                    SUM(CASE WHEN delay_minutes <= :threshold THEN 1 ELSE 0 END) AS on_time,
                    AVG(delay_minutes) AS avg_delay
                FROM flights
                WHERE direction = 'D'
                  AND {NOT_CANCELLED_SQL}
                  AND scheduled_time IS NOT NULL
                  AND delay_minutes IS NOT NULL
                GROUP BY 1
                ORDER BY 1
            """),
            {"threshold": ON_TIME_THRESHOLD_MIN},
        ).fetchall()

        data = [
            {
                "dow": int(r.dow),
                "flights": int(r.flights or 0),
                "on_time_pct": _pct(int(r.on_time or 0), int(r.flights or 0)),
                "avg_delay_minutes": round(float(r.avg_delay), 1) if r.avg_delay is not None else 0.0,
            }
            for r in rows
        ]
        # All 7 days present even if one is empty, so the bar chart never silently loses a day.
        filled = zero_fill(
            data, "dow", list(range(7)),
            template={"flights": 0, "on_time_pct": 0.0, "avg_delay_minutes": 0.0},
        )
        return {"weekdays": filled, "on_time_threshold_minutes": ON_TIME_THRESHOLD_MIN}

    except Exception as e:
        logger.error("Error retrieving weekday insights", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve weekday insights")


@router.get(
    "/by-hour",
    summary="On-time performance by scheduled hour",
    description="Departure punctuality per hour of the day. Cancelled flights are excluded.",
)
async def by_hour(db: Session = Depends(get_db)):
    """Feeds the 'four o'clock wall' card — punctuality bottoms out at 16:00-17:00."""
    try:
        rows = db.execute(
            text(f"""
                SELECT
                    EXTRACT(hour FROM scheduled_time)::int AS hour,
                    COUNT(*) AS flights,
                    SUM(CASE WHEN delay_minutes <= :threshold THEN 1 ELSE 0 END) AS on_time,
                    AVG(delay_minutes) AS avg_delay
                FROM flights
                WHERE direction = 'D'
                  AND {NOT_CANCELLED_SQL}
                  AND scheduled_time IS NOT NULL
                  AND delay_minutes IS NOT NULL
                GROUP BY 1
                ORDER BY 1
            """),
            {"threshold": ON_TIME_THRESHOLD_MIN},
        ).fetchall()

        data = [
            {
                "hour": int(r.hour),
                "flights": int(r.flights or 0),
                "on_time_pct": _pct(int(r.on_time or 0), int(r.flights or 0)),
                "avg_delay_minutes": round(float(r.avg_delay), 1) if r.avg_delay is not None else 0.0,
            }
            for r in rows
        ]
        filled = zero_fill(
            data, "hour", list(range(24)),
            template={"flights": 0, "on_time_pct": 0.0, "avg_delay_minutes": 0.0},
        )
        return {"hours": filled, "on_time_threshold_minutes": ON_TIME_THRESHOLD_MIN}

    except Exception as e:
        logger.error("Error retrieving hourly insights", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve hourly insights")


@router.get(
    "/carrier-recovery",
    summary="Which carriers came back after the disruption, and which did not",
    description=(
        "Each carrier's current schedule as a percentage of its own pre-disruption monthly "
        "average, bucketed into never returned / partial / recovered / expanded."
    ),
)
async def carrier_recovery(
    min_baseline_flights: int = Query(
        MIN_BASELINE_FLIGHTS, ge=1,
        description="Minimum operated departures in the baseline period for a carrier to qualify",
    ),
    db: Session = Depends(get_db),
):
    """
    Feeds the /recovery page. Recomputes on every request, so a carrier resuming next month
    appears without a code change.

    Baseline is each carrier's own pre-disruption average, not a global figure: a carrier that ran
    3 flights a week before and runs 3 a week now has fully recovered, and comparing it against
    El Al's volume would bury that.
    """
    try:
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

    except Exception as e:
        logger.error("Error retrieving carrier recovery", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve carrier recovery")


def _months_between(start_iso: str, end_iso: str) -> float:
    """Whole months between two 'YYYY-MM-01' strings, used to turn a baseline total into a rate."""
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end.year - start.year) * 12 + (end.month - start.month)
