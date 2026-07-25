"""
insights_logic.py — pure aggregation logic behind the /insights and /recovery pages.

Deliberately free of SQLAlchemy and of any PostgreSQL dialect. The endpoints run the raw
per-month / per-carrier aggregation in SQL and hand plain rows to the functions here.

The reason for the split is testability, not tidiness. The backend test suite runs on in-memory
SQLite (see tests/conftest.py), so anything expressed in `date_trunc` / `FILTER` / `to_char` can
only ever be *skipped* under test, never actually verified. The classification rules below are
where every real trap lives, so they must be exercised for real — hence plain functions over
plain dicts.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Iterable, Optional, Sequence, TypedDict


# ---------------------------------------------------------------------------
# Crisis window detection
# ---------------------------------------------------------------------------

class MonthlyRow(TypedDict):
    month: str          # 'YYYY-MM'
    scheduled: int
    cancelled: int


# A month is anomalous when its cancellation rate clears BOTH a hard floor and a multiple of the
# NORMAL rate. The floor alone would misfire on a dataset that happened to be calm throughout; the
# multiple alone would flag an ordinary 2% month in a dataset whose normal rate is 0.5%.
#
# "Normal" is the median of the calmer half of the months, not the median of all of them. Using the
# plain median breaks down exactly when a disruption is long: once crisis months are half the
# dataset the median is itself a crisis month, the threshold inflates past every real value, and
# the function reports no disruption at all on the most disrupted input it will ever see.
CRISIS_FLOOR_PCT = 5.0
CRISIS_MEDIAN_MULTIPLE = 3.0


def cancellation_rate(row: MonthlyRow) -> float:
    """Cancellation percentage for a month. A month with no scheduled flights is 0, not a crash."""
    scheduled = row.get("scheduled") or 0
    if scheduled <= 0:
        return 0.0
    return 100.0 * (row.get("cancelled") or 0) / scheduled


def detect_crisis_window(
    monthly: Sequence[MonthlyRow],
    floor_pct: float = CRISIS_FLOOR_PCT,
    median_multiple: float = CRISIS_MEDIAN_MULTIPLE,
) -> Optional[dict]:
    """
    Derive the disruption window from the data instead of hardcoding March-April 2026.

    Returns {'start': 'YYYY-MM', 'end': 'YYYY-MM', 'months': [...]} for the LONGEST run of
    consecutive anomalous months, or None when nothing clears the bar. Deriving it means the
    shaded region on the chart stays correct through a future disruption with no code edit — and
    equally, that the page does not keep shading March 2026 forever once it is old news.
    """
    if not monthly:
        return None

    ordered = sorted(monthly, key=lambda r: r["month"])
    rates = [cancellation_rate(r) for r in ordered]

    # Trimmed baseline: median of the calmer half, so a long disruption cannot drag the notion of
    # "normal" up to its own level and hide itself.
    calm_half = sorted(rates)[: max(1, len(rates) // 2)]
    baseline_rate = median(calm_half)
    threshold = max(floor_pct, median_multiple * baseline_rate)

    # Collect consecutive runs of anomalous months, then keep the longest.
    runs: list[list[str]] = []
    current: list[str] = []
    for row, rate in zip(ordered, rates):
        if rate >= threshold:
            current.append(row["month"])
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    if not runs:
        return None

    longest = max(runs, key=len)
    return {"start": longest[0], "end": longest[-1], "months": longest, "threshold_pct": round(threshold, 2)}


# ---------------------------------------------------------------------------
# Carrier return / recovery classification
# ---------------------------------------------------------------------------

# A carrier must be dark for at least this long before flying again counts as "coming back".
# Without it, any carrier that simply has no Tuesday service reads as having returned every week.
MIN_GAP_DAYS = 14

# Recovery bucket thresholds, as a percentage of the carrier's own pre-crisis monthly average.
PARTIAL_CEILING_PCT = 90.0
RECOVERED_CEILING_PCT = 125.0

BUCKET_NEVER = "never_returned"
BUCKET_PARTIAL = "partial"
BUCKET_RECOVERED = "recovered"
BUCKET_EXPANDED = "expanded"


def find_return_date(
    active_days: Iterable[date],
    min_gap_days: int = MIN_GAP_DAYS,
    not_before: Optional[date] = None,
) -> Optional[date]:
    """
    First operating day that follows a genuine stoppage, or None if the carrier never stopped.

    `active_days` is every date on which the carrier operated at least one non-cancelled
    departure. Returning None for a continuously-operating carrier is the point: El Al, Arkia and
    Israir flew straight through the disruption, and a naive "first flight after 1 April" query
    reports them as having 'returned' on whatever date the query window happens to open — which
    would put the three carriers that never left at the top of a page about carriers coming back.

    `not_before` restricts the answer to resumptions on or after that date, normally the start of
    the disruption. Seasonal charter operators (Enter Air, Neos, Fly Lili) have perfectly ordinary
    multi-week gaps in their off-season, and without this bound the page reports Enter Air as
    having "returned" on 2025-10-20 — five months before the disruption it is supposedly returning
    from. Such a carrier gets None instead: it is flying, but no distinct return can be identified.
    """
    days = sorted(set(active_days))
    if len(days) < 2:
        return None

    for previous, current in zip(days, days[1:]):
        if (current - previous).days < min_gap_days:
            continue
        if not_before is not None and current < not_before:
            continue
        return current
    return None


class CarrierActivity(TypedDict, total=False):
    airline_code: str
    airline_name: str
    baseline_flights: int      # operated departures across the whole baseline period
    baseline_months: float     # length of that period, in months
    last30_flights: int        # operated departures in the trailing 30 days
    return_date: Optional[date]


def classify_recovery(
    carrier: CarrierActivity,
    partial_ceiling: float = PARTIAL_CEILING_PCT,
    recovered_ceiling: float = RECOVERED_CEILING_PCT,
) -> dict:
    """
    Bucket one carrier by how much of its own pre-crisis schedule it is flying now.

    Bucketing is driven by trailing-30-day volume, NEVER by the presence of a return date. Georgian
    Airways has a first-flight-back date of 2026-04-17 and zero flights since: it is a carrier that
    did not come back, and a rule keyed on the return date would paint it green.
    """
    baseline_flights = carrier.get("baseline_flights") or 0
    baseline_months = carrier.get("baseline_months") or 0
    last30 = carrier.get("last30_flights") or 0

    # Guard the division rather than letting a carrier with no baseline 500 the endpoint.
    baseline_monthly = (baseline_flights / baseline_months) if baseline_months > 0 else 0.0
    recovery_pct = (100.0 * last30 / baseline_monthly) if baseline_monthly > 0 else None

    if last30 <= 0:
        bucket = BUCKET_NEVER
    elif recovery_pct is None:
        # Flying now with no comparable history — new entrant, not a recovery story.
        bucket = BUCKET_RECOVERED
    elif recovery_pct < partial_ceiling:
        bucket = BUCKET_PARTIAL
    elif recovery_pct < recovered_ceiling:
        bucket = BUCKET_RECOVERED
    else:
        bucket = BUCKET_EXPANDED

    return {
        "airline_code": carrier.get("airline_code"),
        "airline_name": carrier.get("airline_name"),
        "baseline_monthly": round(baseline_monthly, 1),
        "last30_flights": last30,
        "recovery_pct": round(recovery_pct, 1) if recovery_pct is not None else None,
        # A carrier that never came back has a return date only in the trivial "flew once" sense;
        # suppress it so the timeline cannot plot a return that did not hold.
        "return_date": carrier.get("return_date").isoformat()
        if carrier.get("return_date") and bucket != BUCKET_NEVER
        else None,
        "bucket": bucket,
    }


# ---------------------------------------------------------------------------
# Zero-filling
# ---------------------------------------------------------------------------

def zero_fill(
    rows: Sequence[dict],
    key: str,
    expected: Sequence,
    template: Optional[dict] = None,
) -> list[dict]:
    """
    Guarantee one row per expected bucket, in order.

    Charts silently drop absent categories, which is the difference between "April had almost no
    foreign departures" and "April is missing from the chart". The former is the story; the latter
    looks like a bug.
    """
    template = template or {}
    by_key = {row[key]: row for row in rows}
    filled = []
    for value in expected:
        if value in by_key:
            filled.append(by_key[value])
        else:
            filled.append({key: value, **template})
    return filled


def month_range(start: str, end: str) -> list[str]:
    """Every 'YYYY-MM' from start to end inclusive, so month charts have no holes."""
    start_year, start_month = (int(p) for p in start.split("-"))
    end_year, end_month = (int(p) for p in end.split("-"))
    months = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months
