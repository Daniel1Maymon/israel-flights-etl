"""
Tests for the pure insights/recovery logic.

No database: these run against plain dicts on purpose, so they actually execute rather than being
skipped under the SQLite test database the way any PostgreSQL-dialect aggregation would be.

The cases named "trap" below are not hypothetical — each one is a wrong answer that the production
data produced during development, before the rule under test existed.
"""
from datetime import date

import pytest

from app.services.carrier_nationality import (
    ISRAELI_CARRIER_CODES,
    nationality_of,
)
from app.services.insights_logic import (
    BUCKET_EXPANDED,
    BUCKET_NEVER,
    BUCKET_PARTIAL,
    BUCKET_RECOVERED,
    cancellation_rate,
    classify_recovery,
    detect_crisis_window,
    find_return_date,
    month_range,
    zero_fill,
)


# ---------------------------------------------------------------------------
# Carrier nationality
# ---------------------------------------------------------------------------

class TestCarrierNationality:
    @pytest.mark.parametrize("code", ["LY", "IZ", "6H", "ER", "E2"])
    def test_israeli_carriers_classified_israeli(self, code):
        assert nationality_of(code) == "israeli"

    @pytest.mark.parametrize("code", ["LH", "BA", "EK", "DL", "U8", "BZ"])
    def test_foreign_carriers_classified_foreign(self, code):
        assert nationality_of(code) == "foreign"

    def test_air_haifa_is_israeli(self):
        """
        Trap: E2 is the easy one to forget. Filed as foreign it flattens the very Israeli/foreign
        gap the insights page is built to show.
        """
        assert "E2" in ISRAELI_CARRIER_CODES
        assert nationality_of("E2") == "israeli"

    def test_case_and_whitespace_insensitive(self):
        assert nationality_of(" ly ") == "israeli"
        assert nationality_of("6h") == "israeli"

    def test_missing_code_is_foreign_not_a_crash(self):
        assert nationality_of(None) == "foreign"
        assert nationality_of("") == "foreign"


# ---------------------------------------------------------------------------
# Crisis window detection
# ---------------------------------------------------------------------------

# Shape of the real production data, rounded: calm months around 1-3%, March catastrophic,
# April elevated, then recovery.
REAL_SHAPE = [
    {"month": "2025-09", "scheduled": 8063, "cancelled": 79},
    {"month": "2025-10", "scheduled": 8982, "cancelled": 113},
    {"month": "2025-11", "scheduled": 7788, "cancelled": 44},
    {"month": "2025-12", "scheduled": 8951, "cancelled": 66},
    {"month": "2026-01", "scheduled": 8455, "cancelled": 207},
    {"month": "2026-02", "scheduled": 7529, "cancelled": 223},
    {"month": "2026-03", "scheduled": 3146, "cancelled": 1776},
    {"month": "2026-04", "scheduled": 2272, "cancelled": 186},
    {"month": "2026-05", "scheduled": 5482, "cancelled": 68},
    {"month": "2026-06", "scheduled": 8697, "cancelled": 137},
    {"month": "2026-07", "scheduled": 9413, "cancelled": 145},
]


class TestDetectCrisisWindow:
    def test_finds_march_april_from_real_shaped_data(self):
        window = detect_crisis_window(REAL_SHAPE)
        assert window is not None
        assert window["start"] == "2026-03"
        assert window["end"] == "2026-04"
        assert window["months"] == ["2026-03", "2026-04"]

    def test_february_below_threshold_is_excluded(self):
        """Feb 2026 sits at ~3% — elevated but not a disruption. It must not widen the window."""
        window = detect_crisis_window(REAL_SHAPE)
        assert "2026-02" not in window["months"]

    def test_calm_dataset_yields_no_window(self):
        calm = [{"month": f"2025-{m:02d}", "scheduled": 1000, "cancelled": 10} for m in range(1, 13)]
        assert detect_crisis_window(calm) is None

    def test_longest_run_wins_over_isolated_spike(self):
        rows = [
            {"month": "2025-01", "scheduled": 1000, "cancelled": 5},
            {"month": "2025-02", "scheduled": 1000, "cancelled": 400},   # isolated 1-month spike
            {"month": "2025-03", "scheduled": 1000, "cancelled": 5},
            {"month": "2025-04", "scheduled": 1000, "cancelled": 300},   # start of a 3-month run
            {"month": "2025-05", "scheduled": 1000, "cancelled": 320},
            {"month": "2025-06", "scheduled": 1000, "cancelled": 280},
            {"month": "2025-07", "scheduled": 1000, "cancelled": 5},
        ]
        window = detect_crisis_window(rows)
        assert window["months"] == ["2025-04", "2025-05", "2025-06"]

    def test_empty_input_returns_none(self):
        assert detect_crisis_window([]) is None

    def test_month_with_zero_scheduled_does_not_divide_by_zero(self):
        rows = [
            {"month": "2026-03", "scheduled": 0, "cancelled": 0},
            {"month": "2026-04", "scheduled": 100, "cancelled": 1},
        ]
        assert cancellation_rate(rows[0]) == 0.0
        detect_crisis_window(rows)  # must not raise

    def test_unordered_input_is_sorted_before_windowing(self):
        window = detect_crisis_window(list(reversed(REAL_SHAPE)))
        assert window["months"] == ["2026-03", "2026-04"]


# ---------------------------------------------------------------------------
# Return date detection
# ---------------------------------------------------------------------------

class TestFindReturnDate:
    def test_continuous_operator_has_no_return_date(self):
        """
        Trap: El Al / Arkia / Israir never stopped flying. A query that simply takes the first
        flight after some cutoff reports them as 'returning' on the cutoff date, putting the three
        carriers that never left at the top of a page about carriers coming back.
        """
        every_day = [date(2026, 3, 1) + __import__("datetime").timedelta(days=i) for i in range(120)]
        assert find_return_date(every_day) is None

    def test_gap_then_resumption_is_detected(self):
        days = [date(2026, 2, 20), date(2026, 2, 25), date(2026, 5, 4), date(2026, 5, 5)]
        assert find_return_date(days) == date(2026, 5, 4)

    def test_short_gap_is_not_a_stoppage(self):
        """A carrier with twice-weekly service has 3-4 day holes; those are not returns."""
        days = [date(2026, 6, 1), date(2026, 6, 5), date(2026, 6, 9), date(2026, 6, 13)]
        assert find_return_date(days) is None

    def test_gap_exactly_at_threshold_counts(self):
        days = [date(2026, 3, 1), date(2026, 3, 15)]
        assert find_return_date(days, min_gap_days=14) == date(2026, 3, 15)

    def test_gap_one_day_under_threshold_does_not_count(self):
        days = [date(2026, 3, 1), date(2026, 3, 14)]
        assert find_return_date(days, min_gap_days=14) is None

    def test_first_gap_wins_when_there_are_several(self):
        days = [date(2026, 1, 1), date(2026, 3, 1), date(2026, 6, 1)]
        assert find_return_date(days) == date(2026, 3, 1)

    def test_single_or_no_activity_returns_none(self):
        assert find_return_date([]) is None
        assert find_return_date([date(2026, 4, 17)]) is None

    def test_duplicate_days_are_collapsed(self):
        days = [date(2026, 3, 1), date(2026, 3, 1), date(2026, 4, 1)]
        assert find_return_date(days) == date(2026, 4, 1)

    def test_seasonal_gap_before_the_disruption_is_not_a_return(self):
        """
        Trap: seasonal charter operators (Enter Air, Neos, Fly Lili) have ordinary multi-week
        off-season gaps. Unbounded, the rule reported Enter Air as returning on 2025-10-20 — five
        months before the disruption it was supposedly returning from.
        """
        days = [
            date(2025, 9, 10),
            date(2025, 10, 20),   # post-off-season resumption, long before the crisis
            date(2025, 10, 25),
            date(2026, 6, 1),     # the real post-crisis resumption
        ]
        assert find_return_date(days, not_before=date(2026, 3, 1)) == date(2026, 6, 1)

    def test_not_before_yields_none_when_only_pre_crisis_gaps_exist(self):
        """Flying, but with no identifiable return — better than naming a misleading date."""
        days = [date(2025, 9, 10), date(2025, 10, 20), date(2025, 10, 25)]
        assert find_return_date(days, not_before=date(2026, 3, 1)) is None

    def test_not_before_is_inclusive(self):
        days = [date(2026, 2, 1), date(2026, 3, 1)]
        assert find_return_date(days, not_before=date(2026, 3, 1)) == date(2026, 3, 1)


# ---------------------------------------------------------------------------
# Recovery bucketing
# ---------------------------------------------------------------------------

def carrier(**kwargs):
    base = {
        "airline_code": "XX",
        "airline_name": "TEST AIR",
        "baseline_flights": 600,   # 100/month across 6 months
        "baseline_months": 6,
        "last30_flights": 100,
        "return_date": None,
    }
    base.update(kwargs)
    return base


class TestClassifyRecovery:
    def test_no_recent_flights_is_never_returned(self):
        result = classify_recovery(carrier(last30_flights=0))
        assert result["bucket"] == BUCKET_NEVER

    def test_georgian_airways_trap_return_date_but_no_flights(self):
        """
        Trap: a carrier that flew once on 2026-04-17 and never again has a legitimate return date
        but zero trailing-30-day flights. Bucketing keyed on the return date paints it as back;
        it must read as never returned, and the stale return date must be suppressed so the
        timeline cannot plot a return that did not hold.
        """
        result = classify_recovery(
            carrier(last30_flights=0, return_date=date(2026, 4, 17))
        )
        assert result["bucket"] == BUCKET_NEVER
        assert result["return_date"] is None

    def test_partial_recovery(self):
        result = classify_recovery(carrier(last30_flights=67))  # 67% of baseline
        assert result["bucket"] == BUCKET_PARTIAL
        assert result["recovery_pct"] == 67.0

    def test_full_recovery(self):
        assert classify_recovery(carrier(last30_flights=105))["bucket"] == BUCKET_RECOVERED

    def test_expansion_into_the_gap(self):
        result = classify_recovery(carrier(last30_flights=381))
        assert result["bucket"] == BUCKET_EXPANDED
        assert result["recovery_pct"] == 381.0

    def test_return_date_preserved_for_carriers_that_did_come_back(self):
        result = classify_recovery(
            carrier(last30_flights=100, return_date=date(2026, 5, 17))
        )
        assert result["return_date"] == "2026-05-17"

    def test_zero_baseline_does_not_divide_by_zero(self):
        result = classify_recovery(
            carrier(baseline_flights=0, baseline_months=0, last30_flights=12)
        )
        assert result["recovery_pct"] is None
        assert result["bucket"] == BUCKET_RECOVERED  # flying, but no history to compare against

    def test_bucket_boundaries(self):
        assert classify_recovery(carrier(last30_flights=89))["bucket"] == BUCKET_PARTIAL
        assert classify_recovery(carrier(last30_flights=90))["bucket"] == BUCKET_RECOVERED
        assert classify_recovery(carrier(last30_flights=124))["bucket"] == BUCKET_RECOVERED
        assert classify_recovery(carrier(last30_flights=125))["bucket"] == BUCKET_EXPANDED


# ---------------------------------------------------------------------------
# Zero-filling
# ---------------------------------------------------------------------------

class TestZeroFill:
    def test_missing_buckets_are_filled_not_dropped(self):
        """
        April 2026 had almost no foreign departures. A chart that omits the bar reads as a broken
        chart; a chart with a near-zero bar reads as the story.
        """
        rows = [{"month": "2026-03", "flights": 1284}]
        filled = zero_fill(rows, "month", ["2026-03", "2026-04"], template={"flights": 0})
        assert len(filled) == 2
        assert filled[1] == {"month": "2026-04", "flights": 0}

    def test_order_follows_expected_not_input(self):
        rows = [{"h": 5, "n": 1}, {"h": 1, "n": 2}]
        filled = zero_fill(rows, "h", [1, 2, 3, 4, 5], template={"n": 0})
        assert [r["h"] for r in filled] == [1, 2, 3, 4, 5]
        assert filled[1]["n"] == 0

    def test_all_24_hours_present(self):
        filled = zero_fill([{"hour": 9, "n": 3}], "hour", list(range(24)), template={"n": 0})
        assert len(filled) == 24

    def test_all_seven_weekdays_present(self):
        filled = zero_fill([{"dow": 6, "n": 3}], "dow", list(range(7)), template={"n": 0})
        assert len(filled) == 7


class TestMonthRange:
    def test_spans_year_boundary(self):
        assert month_range("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]

    def test_single_month(self):
        assert month_range("2026-03", "2026-03") == ["2026-03"]

    def test_full_production_window_has_no_holes(self):
        months = month_range("2025-09", "2026-07")
        assert len(months) == 11
        assert months[0] == "2025-09" and months[-1] == "2026-07"
