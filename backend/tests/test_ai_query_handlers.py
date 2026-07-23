"""
Integration tests for AI-search query handlers (run against the real DB via the read-only role).

Uses tolerant assertions (the flights table updates live, so exact counts drift). Verifies:
- handlers return sane, correctly-shaped metrics,
- the min-10 sample rule is enforced (Adversarial §8),
- sort direction works,
- everything runs through the least-privilege rankair_ro connection.

Skipped automatically if DATABASE_URL_RO is not configured.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL_RO"), reason="DATABASE_URL_RO not set (read-only role)"
)

from app.services import ai_query_handlers as B  # noqa: E402


def test_rank_airlines_london_is_sane():
    cols, rows = B.rank_airlines({"intent": "rank_airlines", "destination": "London",
                                  "metric": "on_time", "sort": "desc"})
    assert rows, "expected airlines to London"
    for r in rows:
        assert r["total_flights"] >= 10                    # min-sample rule enforced
        assert 0 <= r["on_time_pct"] <= 100
    names = {r["airline_name"] for r in rows}
    assert any("BRITISH AIRWAYS" in n for n in names)


def test_min_sample_enforced_overall():
    _, rows = B.overall({"intent": "overall", "metric": "on_time"})
    assert rows
    assert all(r["total_flights"] >= 10 for r in rows)     # no 1-flight "100%" noise


def test_cancel_sort_ascending():
    _, rows = B.rank_airlines({"intent": "rank_airlines", "destination": "Paris",
                               "metric": "cancel", "sort": "asc"})
    vals = [r["cancel_pct"] for r in rows if r["cancel_pct"] is not None]
    assert vals == sorted(vals)                            # ascending by cancel %


def test_head_to_head_two_airlines():
    _, rows = B.head_to_head({"intent": "head_to_head", "destination": "Athens",
                              "airlines": ["EL AL", "WIZZ"]})
    assert len(rows) <= 2
    for r in rows:
        assert r["total_flights"] >= 10


def test_by_destination_groups_by_city():
    cols, rows = B.by_destination({"intent": "by_destination", "airlines": ["EL AL"]})
    assert "destination" in cols
    assert rows


def test_by_region_europe():
    _, rows = B.by_region({"intent": "by_region", "region": "Europe", "metric": "on_time"})
    assert rows


def test_no_handler_match_raises():
    with pytest.raises(B.NoQueryHandlerMatch):
        B.run_query_handler({"intent": "trend_by_weekday"})
