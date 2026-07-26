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
    cols, rows, meta = B.rank_airlines({"intent": "rank_airlines", "destination": "London",
                                  "metric": "on_time", "sort": "desc"})
    assert rows, "expected airlines to London"
    for r in rows:
        assert r["total_flights"] >= 10                    # min-sample rule enforced
        assert 0 <= r["on_time_pct"] <= 100
    names = {r["airline_name"] for r in rows}
    assert any("BRITISH AIRWAYS" in n for n in names)


def test_min_sample_enforced_overall():
    _, rows, meta = B.overall({"intent": "overall", "metric": "on_time"})
    assert rows
    assert all(r["total_flights"] >= 10 for r in rows)     # no 1-flight "100%" noise


def test_best_first_is_fewest_cancellations():
    """'best' for the cancel metric means the LOWEST rate — the handler owns that inversion now."""
    _, rows, meta = B.rank_airlines({"intent": "rank_airlines", "destination": "Paris",
                                     "metric": "cancel", "superlative": "best"})
    vals = [r["cancel_pct"] for r in rows if r["cancel_pct"] is not None]
    assert vals == sorted(vals)
    assert meta["ordered_by"] == "fewest cancellations first"


def test_worst_first_inverts_it():
    _, rows, meta = B.rank_airlines({"intent": "rank_airlines", "destination": "Paris",
                                     "metric": "cancel", "superlative": "worst"})
    vals = [r["cancel_pct"] for r in rows if r["cancel_pct"] is not None]
    assert vals == sorted(vals, reverse=True)
    assert meta["ordered_by"] == "most cancellations first"


def test_ranking_reports_how_much_it_left_out():
    _, rows, meta = B.overall({"intent": "overall", "metric": "on_time", "limit": 10})
    assert meta["returned"] == len(rows)
    assert meta["total_matching"] > len(rows), "more carriers exist than were returned"
    assert meta["truncated"] is True
    assert meta["min_sample"] == 10


def test_head_to_head_two_airlines():
    _, rows, meta = B.head_to_head({"intent": "head_to_head", "destination": "Athens",
                              "airlines": ["EL AL", "WIZZ"]})
    assert len(rows) <= 2
    for r in rows:
        assert r["total_flights"] >= 10


def test_by_destination_groups_by_city():
    cols, rows, meta = B.by_destination({"intent": "by_destination", "airlines": ["EL AL"]})
    assert "destination" in cols
    assert rows


def test_by_region_europe():
    _, rows, meta = B.by_region({"intent": "by_region", "region": "Europe", "metric": "on_time"})
    assert rows


def test_no_handler_match_raises():
    with pytest.raises(B.NoQueryHandlerMatch):
        B.run_query_handler({"intent": "trend_by_weekday"})
