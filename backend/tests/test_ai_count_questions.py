"""
AI search must answer "how many …" questions with the SAME number the dashboard shows.

THE BUG THIS PINS DOWN
    "כמה המראות היו בנתב\"ג?" (how many departures at TLV) was classified intent="overall",
    which routed it to the overall handler — a handler that ignores the question and always
    returns airlines ranked by on-time %, LIMIT 10. The format LLM then summed those ten rows
    and answered "7,553 departures". The true figure was 79,412: wrong by 10.5x, and wrong in
    kind, since the ten carriers were selected by punctuality, which the question never asked
    about. `overall` is greedy — it captures any airline-wide question and answers a
    punctuality question regardless of what was asked.

THE ORACLE
    app/api/stats.py (GET /api/v1/stats/overview) — the dashboard's headline bar. It is the
    authority, so these tests never hardcode a count: they recompute its SQL and compare. That
    also settles the past/future question — the dashboard applies NO time filter, so a
    departure scheduled for next week counts. AI search agreeing with itself but disagreeing
    with the bar on the same page IS the defect.

LAYERS
    1. unit   — routing and SQL shape, no LLM and no DB (always run)
    2. db     — handler output == the dashboard's own SQL (needs DATABASE_URL_RO)
    3. live   — the real LLM, repeated, since interpretation is the stochastic part that broke
                (needs DATABASE_URL_RO + GEMINI_API_KEY; run with -m llm)
"""
from __future__ import annotations

import os
import re

import pytest

from app.services import ai_query_handlers as H
from app.services.ai_query_handlers import NoQueryHandlerMatch

needs_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL_RO"), reason="DATABASE_URL_RO not set (read-only role)"
)
needs_llm = pytest.mark.skipif(
    not (os.getenv("DATABASE_URL_RO") and os.getenv("GEMINI_API_KEY")),
    reason="live LLM test: needs DATABASE_URL_RO + GEMINI_API_KEY",
)

# The dashboard's own SQL, copied from app/api/stats.py. Duplicated deliberately: if someone
# changes how the bar counts, this must fail rather than silently follow along.
DASHBOARD_SQL = """
    SELECT
        COUNT(*) FILTER (WHERE direction = 'D') AS departures,
        COUNT(*) FILTER (WHERE direction = 'A') AS arrivals,
        COUNT(*) AS total,
        COUNT(DISTINCT airline_name) FILTER (
            WHERE direction = 'D' AND airline_name IS NOT NULL AND TRIM(airline_name) != ''
        ) AS airlines,
        COUNT(DISTINCT location_city_en) FILTER (
            WHERE direction = 'D' AND location_city_en IS NOT NULL AND TRIM(location_city_en) != ''
        ) AS destinations
    FROM flights
"""


@pytest.fixture(scope="module")
def dashboard():
    """The headline numbers AI search must reproduce."""
    from app.services.ai_db import run_readonly

    _, rows = run_readonly(DASHBOARD_SQL)
    return rows[0]


# --- layer 1: routing and shape ------------------------------------------------------------

def test_count_intent_is_registered():
    assert "count" in H._HANDLERS, "a count question must have a reviewed handler to land on"


def test_count_handler_is_reachable_through_the_router(monkeypatch):
    seen = {}
    monkeypatch.setitem(H._HANDLERS, "count", lambda i: seen.setdefault("intent", i) and ([], []))
    H.run_query_handler({"intent": "count", "count_of": "flights"})
    assert seen["intent"]["intent"] == "count"


@pytest.mark.parametrize(
    "count_of,direction,expect_sql",
    [
        ("flights", "departures", "COUNT(*)"),
        ("flights", "arrivals", "COUNT(*)"),
        ("flights", None, "COUNT(*)"),
        ("airlines", None, "COUNT(DISTINCT airline_name)"),
        ("destinations", None, "COUNT(DISTINCT location_city_en)"),
    ],
)
def test_count_handler_emits_the_dashboards_aggregate(monkeypatch, count_of, direction, expect_sql):
    captured = {}
    monkeypatch.setattr(H, "_run", lambda sql, params: captured.update(sql=sql, params=params) or ([], []))
    H.count_entities({"intent": "count", "count_of": count_of, "direction": direction})
    assert expect_sql in captured["sql"]
    # Never the min-sample rule: it exists to suppress noisy per-airline percentages and would
    # silently drop small carriers from a total.
    assert "HAVING" not in captured["sql"].upper()
    # Never a time filter: the dashboard applies none, so neither may this.
    assert "now()" not in captured["sql"].lower()


@pytest.mark.parametrize("direction,expected", [("departures", "'D'"), ("arrivals", "'A'")])
def test_flight_count_respects_an_explicit_direction(monkeypatch, direction, expected):
    captured = {}
    monkeypatch.setattr(H, "_run", lambda sql, params: captured.update(sql=sql) or ([], []))
    H.count_entities({"intent": "count", "count_of": "flights", "direction": direction})
    assert f"direction = {expected}" in captured["sql"]


def test_flight_count_without_a_direction_counts_everything(monkeypatch):
    captured = {}
    monkeypatch.setattr(H, "_run", lambda sql, params: captured.update(sql=sql) or ([], []))
    H.count_entities({"intent": "count", "count_of": "flights", "direction": None})
    assert "direction" not in captured["sql"], "unqualified 'how many flights' is the dashboard total"


def test_airlines_and_destinations_are_departures_scoped(monkeypatch):
    """The dashboard scopes both to departures; matching it is the whole point."""
    for count_of in ("airlines", "destinations"):
        captured = {}
        monkeypatch.setattr(H, "_run", lambda sql, params: captured.update(sql=sql) or ([], []))
        H.count_entities({"intent": "count", "count_of": count_of, "direction": None})
        assert "direction = 'D'" in captured["sql"]


def test_unknown_count_target_is_declined(monkeypatch):
    # Better to fall through to the guarded fallback than to answer a different question.
    with pytest.raises(NoQueryHandlerMatch):
        H.count_entities({"intent": "count", "count_of": "terminals"})


def test_count_returns_exactly_one_row(monkeypatch):
    monkeypatch.setattr(H, "_run", lambda sql, params: (["total_flights"], [{"total_flights": 79412}]))
    cols, rows = H.count_entities({"intent": "count", "count_of": "flights"})
    assert len(rows) == 1 and len(cols) == 1


def test_count_columns_survive_the_public_relabelling(monkeypatch):
    """A count column dropped by the label filter would leave the LLM with an empty row."""
    from app.services.ai_search import _to_public_columns

    for count_of, alias in [("flights", "total_flights"), ("airlines", "total_airlines"),
                            ("destinations", "total_destinations")]:
        monkeypatch.setattr(H, "_run", lambda sql, params, a=alias: ([a], [{a: 1234}]))
        cols, rows = H.count_entities({"intent": "count", "count_of": count_of})
        public_cols, public_rows = _to_public_columns(cols, rows)
        assert len(public_cols) == 1, f"{alias} was dropped at the public boundary"
        assert list(public_rows[0].values()) == [1234]


# --- layer 2: the handler agrees with the dashboard ----------------------------------------

@needs_db
@pytest.mark.parametrize(
    "count_of,direction,dashboard_key",
    [
        ("flights", "departures", "departures"),
        ("flights", "arrivals", "arrivals"),
        ("flights", None, "total"),
        ("airlines", None, "airlines"),
        ("destinations", None, "destinations"),
    ],
)
def test_handler_matches_the_dashboard_exactly(dashboard, count_of, direction, dashboard_key):
    _, rows = H.count_entities({"intent": "count", "count_of": count_of, "direction": direction})
    assert list(rows[0].values())[0] == dashboard[dashboard_key]


@needs_db
def test_the_regression_number_is_nowhere_near_the_truth(dashboard):
    """The shipped answer was 7,553. Guard the order of magnitude, not just equality."""
    _, rows = H.count_entities({"intent": "count", "count_of": "flights", "direction": "departures"})
    assert list(rows[0].values())[0] > 50_000


# --- layer 3: the live LLM, repeated -------------------------------------------------------

COUNT_QUESTIONS = [
    ('כמה המראות היו בנתב"ג?', "departures"),
    ("how many departures were there at Ben Gurion?", "departures"),
    ('כמה נחיתות היו בנתב"ג?', "arrivals"),
    ("how many airlines fly out of Tel Aviv?", "airlines"),
    ("how many destinations can you fly to from TLV?", "destinations"),
]

# The interpretation step is what failed, and it is stochastic — one green run proves nothing.
LIVE_REPEATS = int(os.getenv("AI_LIVE_REPEATS", "3"))

# Carriers the buggy path named. They come from ORDER BY on_time_pct DESC and have no business
# in an answer about how many flights there were.
RANKING_LEAKAGE = ("SKYUP", "FLYDUBAI", "ETIHAD", "EMIRATES", "AZERBAIJAN", "UZBEKISTAN")


def _numbers_in(text: str) -> set[int]:
    """Every integer in the prose, with thousands separators (7,553 / 7553 / 7 553) normalised."""
    return {int(re.sub(r"[,\s']", "", m)) for m in re.findall(r"\d[\d,\s']*\d|\d", text)}


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("question,dashboard_key", COUNT_QUESTIONS)
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_live_count_answer_matches_the_dashboard(dashboard, question, dashboard_key, run):
    from app.services.ai_search import answer_question

    expected = dashboard[dashboard_key]
    resp, _ = answer_question(question)

    assert not resp.refused, f"refused ({resp.reason}): {question}"
    assert resp.source == "handler", "a headline count must not be left to generated SQL"
    assert len(resp.rows) == 1, f"a count is one number, got {len(resp.rows)} rows"
    assert list(resp.rows[0].values())[0] == expected

    assert expected in _numbers_in(resp.answer), (
        f"prose must state {expected:,}; got: {resp.answer}"
    )
    assert not any(c in (resp.answer or "").upper() for c in RANKING_LEAKAGE), (
        f"on-time ranking leaked into a count answer: {resp.answer}"
    )


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_live_count_is_not_captured_by_overall(run):
    """The specific misrouting that produced 7,553."""
    from app.services.llm_tasks import LLMTasks

    intent, _ = LLMTasks().interpret('כמה המראות היו בנתב"ג?')
    assert intent.intent == "count", f"still routed to {intent.intent!r}"
    assert intent.count_of == "flights"
    assert intent.direction == "departures"


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_live_ranking_questions_still_reach_overall(run):
    """Tightening `overall` must not break what it was actually for."""
    from app.services.llm_tasks import LLMTasks

    intent, _ = LLMTasks().interpret("which airlines are the most punctual overall?")
    assert intent.intent in ("overall", "rank_airlines")
