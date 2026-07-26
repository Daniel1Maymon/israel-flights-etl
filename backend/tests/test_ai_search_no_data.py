"""
Tests for the empty-result path and the SQL prompt's temporal grounding.

An empty result must be reported as a typed reason with the data's coverage window, NOT narrated
by the LLM as "no data was found" — that prose is indistinguishable from a genuine zero-match and
costs a call that had nothing to work with. And the SQL prompt must carry the real window, since a
model that doesn't know the range writes date-blind queries.

Fully mocked: no LLM key and no DB required.
"""
from datetime import date, datetime

import pytest

from app.schemas.ai_search import Intent
from app.services import ai_db, ai_search, llm_tasks
from app.services.ai_query_handlers import NoQueryHandlerMatch


VALID_INTENT = Intent(
    valid=True, intent="overall", destination=None, airlines=[], region=None,
    metric="on_time", count_of=None, direction=None, recovery_bucket=None,
    superlative=None, limit=10,
)


class _FakeTasks:
    """Stands in for LLMTasks; records whether format_answer was ever reached."""

    def __init__(self, sql: str = "SELECT airline_name FROM flights LIMIT 10") -> None:
        self._sql = sql
        self.formatted = False

    def interpret(self, question):
        return VALID_INTENT, 10

    def generate_sql(self, question):
        return self._sql, 20

    def format_answer(self, question, rows, meta=None):
        self.formatted = True
        return "some prose", 30


@pytest.fixture
def window(monkeypatch):
    """Pin the coverage window so assertions don't depend on live data."""
    w = (date(2025, 9, 5), date(2026, 7, 28))
    monkeypatch.setattr(ai_db, "get_data_window", lambda: w)
    monkeypatch.setattr(ai_search, "get_data_window", lambda: w)
    monkeypatch.setattr(llm_tasks, "get_data_window", lambda: w)
    return w


def _run(monkeypatch, *, rows, handler_matches=True, tasks=None):
    tasks = tasks or _FakeTasks()
    monkeypatch.setattr(ai_search, "LLMTasks", lambda *a, **k: tasks)

    def fake_handler(intent):
        if not handler_matches:
            raise NoQueryHandlerMatch("no handler")
        return (["airline_name"], rows, {})

    monkeypatch.setattr(ai_search, "run_query_handler", fake_handler)
    monkeypatch.setattr(ai_search, "run_readonly", lambda sql, params=None: (["airline_name"], rows))
    monkeypatch.setattr(ai_search, "validate_and_prepare", lambda sql, n: sql)
    return ai_search.answer_question("איזה חברות עוד לא חזרו לטוס לישראל?"), tasks


def test_empty_handler_result_is_typed_not_narrated(monkeypatch, window):
    (resp, _), tasks = _run(monkeypatch, rows=[])
    assert resp.refused and resp.reason == "no_data"
    assert not tasks.formatted, "format_answer must not be called with zero rows"
    assert resp.answer is None


def test_empty_result_reports_the_coverage_window(monkeypatch, window):
    (resp, _), _ = _run(monkeypatch, rows=[])
    assert (resp.data_start, resp.data_end) == ("2025-09-05", "2026-07-28")


def test_empty_result_keeps_the_source_for_analytics(monkeypatch, window):
    (resp, _), _ = _run(monkeypatch, rows=[], handler_matches=False)
    assert resp.source == "fallback"     # ai_events still records which path produced nothing


def test_unreadable_window_degrades_to_null_dates(monkeypatch):
    monkeypatch.setattr(ai_search, "get_data_window", lambda: None)
    (resp, _), _ = _run(monkeypatch, rows=[])
    assert resp.reason == "no_data"
    assert resp.data_start is None and resp.data_end is None   # no window is better than a wrong one


def test_nonempty_result_still_gets_prose(monkeypatch, window):
    (resp, _), tasks = _run(monkeypatch, rows=[{"airline_name": "EL AL"}])
    assert not resp.refused
    assert tasks.formatted and resp.answer == "some prose"


def test_sql_prompt_states_todays_date_and_the_window(monkeypatch, window):
    prompt = llm_tasks._sql_sys()
    assert "2025-09-05" in prompt and "2026-07-28" in prompt
    assert date.today().isoformat() in prompt
    assert "no roster of airlines that once served TLV" in prompt


def test_sql_prompt_omits_context_when_window_is_unreadable(monkeypatch):
    monkeypatch.setattr(llm_tasks, "get_data_window", lambda: None)
    prompt = llm_tasks._sql_sys()
    assert "Data context" not in prompt
    assert prompt.startswith("Translate the question")   # still a usable prompt


def test_data_window_is_cached(monkeypatch):
    calls = []

    def fake_run(sql, params=None):
        calls.append(sql)
        return ["lo", "hi"], [{"lo": datetime(2025, 9, 5), "hi": datetime(2026, 7, 28)}]

    monkeypatch.setattr(ai_db, "_window_cache", None)
    monkeypatch.setattr(ai_db, "run_readonly", fake_run)
    assert ai_db.get_data_window() == (date(2025, 9, 5), date(2026, 7, 28))
    ai_db.get_data_window()
    assert len(calls) == 1, "window query must not run on every request"


def test_data_window_returns_none_when_db_is_down(monkeypatch):
    def boom(sql, params=None):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(ai_db, "_window_cache", None)
    monkeypatch.setattr(ai_db, "run_readonly", boom)
    assert ai_db.get_data_window() is None


# --- carrier_recovery: the one question no SELECT over `flights` can answer -----------------

_RECOVERY_FIXTURE = {
    "crisis_window": {"start": "2026-03", "end": "2026-04"},
    "carriers": [
        {"airline_name": "BRITISH AIRWAYS PLC", "baseline_monthly": 20.8, "last30_flights": 0,
         "recovery_pct": 0.0, "return_date": None, "bucket": "never_returned"},
        {"airline_name": "TRANSAVIA FRANCE", "baseline_monthly": 63.8, "last30_flights": 0,
         "recovery_pct": 0.0, "return_date": None, "bucket": "never_returned"},
        {"airline_name": "EL AL", "baseline_monthly": 900.0, "last30_flights": 1000,
         "recovery_pct": 111.0, "return_date": "2026-04-10", "bucket": "expanded"},
    ],
}


@pytest.fixture
def recovery(monkeypatch):
    from app.services import ai_query_handlers as h

    monkeypatch.setattr(h, "get_ro_engine", lambda: None)
    monkeypatch.setattr(h, "sessionmaker", lambda bind=None: lambda: _NullSession())
    monkeypatch.setattr(h, "compute_carrier_recovery", lambda db: _RECOVERY_FIXTURE)
    return h


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_carrier_recovery_returns_the_absent_carriers(recovery):
    cols, rows = recovery.carrier_recovery({"intent": "carrier_recovery", "limit": 10})
    assert [r["airline_name"] for r in rows] == ["TRANSAVIA FRANCE", "BRITISH AIRWAYS PLC"]
    assert "EL AL" not in str(rows)                       # expanded carriers are not "not back"
    assert cols[0] == "airline_name"


def test_carrier_recovery_defaults_to_never_returned(recovery):
    _, unset = recovery.carrier_recovery({"intent": "carrier_recovery"})
    _, junk = recovery.carrier_recovery({"intent": "carrier_recovery", "recovery_bucket": "nonsense"})
    assert len(unset) == 2 and len(junk) == 2


def test_carrier_recovery_honours_the_requested_bucket(recovery):
    _, rows = recovery.carrier_recovery({"intent": "carrier_recovery", "recovery_bucket": "expanded"})
    assert [r["airline_name"] for r in rows] == ["EL AL"]


def test_carrier_recovery_biggest_carriers_first(recovery):
    _, rows = recovery.carrier_recovery({"intent": "carrier_recovery"})
    assert rows[0]["baseline_monthly"] > rows[1]["baseline_monthly"]


def test_carrier_recovery_declines_when_no_disruption_is_detectable(recovery, monkeypatch):
    monkeypatch.setattr(
        recovery, "compute_carrier_recovery",
        lambda db: {"carriers": [], "crisis_window": None, "summary": {}},
    )
    # Better to fall through than to publish a list built off an invented cutoff.
    with pytest.raises(NoQueryHandlerMatch):
        recovery.carrier_recovery({"intent": "carrier_recovery"})


def test_carrier_recovery_is_routed_from_the_intent(recovery):
    cols, rows, _meta = recovery.run_query_handler({"intent": "carrier_recovery", "limit": 5})
    assert rows and "recovery_pct" in cols


def test_recovery_columns_survive_the_public_relabelling(recovery):
    from app.services.ai_search import _to_public_columns

    cols, rows = recovery.carrier_recovery({"intent": "carrier_recovery"})
    public_cols, public_rows = _to_public_columns(cols, rows)
    assert len(public_cols) == len(cols), "no recovery column may be silently dropped"
    assert "Recovery %" in public_cols and "Airline" in public_cols
    assert all(len(r) == len(cols) for r in public_rows)
