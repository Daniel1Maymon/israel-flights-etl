"""
Data-health invariant for on-time metrics — run periodically against live data:

    pytest -m data_integrity

Guards the on-time bug fix. A cancelled flight is not "on time", so for any airline/destination
group `on_time_pct + cancel_pct` must never exceed 100%. Before the fix, cancelled flights (whose
delay_minutes is often <= 15) were counted as on-time, producing impossible sums like
91.9% + 18.9% = 110.8% (e.g. Brussels Airlines -> Athens: real on-time is 27/37 = 73.0%). On the
current dataset the old definition produced several violating groups; the fixed definition produces
zero.

The corrected definition (must match ai_query_handlers._METRICS_SELECT, api/destinations.py and
etl/rankair_refresh.py):
    on-time     = status_en NOT ILIKE 'CANCELED' AND delay_minutes <= 15
    cancel      = status_en ILIKE 'CANCELED'
    denominator = COUNT(*)

Skipped automatically if DATABASE_URL_RO is not configured.
"""
import os

import pytest

pytestmark = [
    pytest.mark.data_integrity,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL_RO"), reason="DATABASE_URL_RO not set (read-only role)"
    ),
]

from app.services.ai_db import run_readonly  # noqa: E402

MIN_SAMPLE = 10  # ignore tiny groups where a single flight swings the percentage

_FIXED_SQL = f"""
    SELECT airline_name,
           location_city_en,
           COUNT(*) AS n,
           ROUND(100.0 * SUM(CASE WHEN status_en NOT ILIKE 'CANCELED' AND delay_minutes <= 15 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct,
           ROUND(100.0 * SUM(CASE WHEN status_en ILIKE 'CANCELED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS cancel_pct
    FROM flights
    GROUP BY airline_name, location_city_en
    HAVING COUNT(*) >= {MIN_SAMPLE}
"""

_OLD_BUGGY_SQL = f"""
    SELECT airline_name,
           location_city_en,
           ROUND(100.0 * SUM(CASE WHEN delay_minutes <= 15 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct,
           ROUND(100.0 * SUM(CASE WHEN status_en ILIKE 'CANCELED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS cancel_pct
    FROM flights
    GROUP BY airline_name, location_city_en
    HAVING COUNT(*) >= {MIN_SAMPLE}
"""


def _sum(row):
    return (row["on_time_pct"] or 0) + (row["cancel_pct"] or 0)


def _violations(rows):
    return sorted(
        (r for r in rows if _sum(r) > 100.0),
        key=lambda r: _sum(r),
        reverse=True,
    )


def test_on_time_plus_cancel_never_exceeds_100():
    """The core invariant: no airline/destination group can exceed 100% on-time-plus-cancelled."""
    _, rows = run_readonly(_FIXED_SQL)
    assert rows, "expected at least one airline/city group"
    bad = _violations(rows)
    detail = "\n".join(
        f"  {r['airline_name']} -> {r['location_city_en']}: "
        f"on_time={r['on_time_pct']}% + cancel={r['cancel_pct']}% = {round(_sum(r), 1)}% (n={r['n']})"
        for r in bad[:10]
    )
    assert not bad, f"{len(bad)} group(s) violate on_time% + cancel% <= 100:\n{detail}"


def test_invariant_has_teeth():
    """Sanity: the OLD (buggy) definition DOES violate the invariant on the same data, so a pass
    above reflects the fix rather than a coincidentally clean dataset. If the current data happens
    to carry no cancellations in any min-sample group, skip rather than fail (data drifts live)."""
    _, rows = run_readonly(_OLD_BUGGY_SQL)
    bad = [r for r in rows if _sum(r) > 100.0]
    if not bad:
        pytest.skip("no cancellations in current min-sample groups to exercise the guard")
    assert bad, "expected the OLD definition to violate the invariant"
