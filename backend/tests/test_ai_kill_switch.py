"""
The manual kill switch: an admin flips one row in ai_flags, and the LLM stops being called.

Three things are pinned here.

The guarantee — when the flag is off, `answer_question` is never reached. That is what "no LLM
calls" means in practice; a refusal that still spent a Gemini call on the way would defeat the
whole feature. It sits ABOVE the daily cap in the ladder for a second reason tested below: a user
must not lose one of their ten daily questions to a feature that is switched off.

The words — an off switch says so, in the asker's language. Under the generic refusal a visitor
reads "I don't have data that answers that" and concludes the product is empty, which is the same
mistake the daily cap already made once (see refusal_text.py).

The gate — the toggle is a WRITE reachable from the public internet, so an unauthenticated caller
must never flip it, and no response may hand back the token that would let them.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.main import app
from app.schemas.ai_search import AISearchResponse
from app.services.ai_flags import ensure_flags_table, is_llm_enabled, set_llm_enabled
from app.services.refusal_text import _GENERIC, off_text

ADMIN_TOKEN = "test-admin-token"
ENDPOINT = "/api/v1/admin/llm"


@pytest.fixture
def flags_db():
    """A real (SQLite) database carrying the real DDL — so the shipped CREATE TABLE is exercised."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    ensure_flags_table(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _admin(token: str | None = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


# --------------------------------------------------------------------------------------
# the flag itself
# --------------------------------------------------------------------------------------


def test_a_missing_row_reads_as_on(flags_db):
    """
    A fresh deploy must not ship with the feature dark.

    This is the one place the codebase deliberately fails OPEN rather than closed (admin_token
    does the opposite). The risk here is only cost, and cost is already bounded by the monthly
    budget and the per-user cap; the risk of failing closed is a working feature silently
    disappearing on a deploy, with nothing in the UI to say why.
    """
    flags_db.execute(text("DELETE FROM ai_flags"))
    flags_db.commit()
    assert is_llm_enabled(flags_db) is True


def test_the_ddl_seeds_the_switch_on(flags_db):
    """ensure_flags_table is what a fresh deploy runs; it must leave the feature usable."""
    assert is_llm_enabled(flags_db) is True


def test_an_unreadable_flag_table_does_not_take_the_feature_down():
    """
    The switch must not be able to break the thing it guards.

    Startup DDL is best-effort — app.main logs and carries on if the database was briefly
    unreachable — so the table can genuinely be absent. This check runs FIRST in the guard ladder,
    so an exception here is not a refusal, it is a 500 on every question. Degrade to on instead,
    where the monthly budget and the daily cap still bound the damage.
    """
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db = sessionmaker(bind=engine)()  # no ensure_flags_table: the table is missing
    try:
        assert is_llm_enabled(db) is True
        # ...and the session is still usable, or the budget check and analytics write that follow
        # would fail too (a failed statement aborts the transaction on Postgres).
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        db.close()


def test_the_flag_round_trips_through_the_database(flags_db):
    """The DB row is the source of truth -- what was written is what is read back."""
    set_llm_enabled(flags_db, False, note="token spike")
    assert is_llm_enabled(flags_db) is False

    set_llm_enabled(flags_db, True, note=None)
    assert is_llm_enabled(flags_db) is True


def test_no_llm_call_site_appears_outside_the_guarded_path():
    """
    Why ONE check, in the endpoint, is enough — and the thing that must stay true for it to be.

    The switch is enforced in api/ai_search.py only. That covers everything as long as every route
    to a provider runs underneath answer_question(), which the endpoint calls after the check. Two
    files reach a provider today and both satisfy that:

        services/ai_search.py           answer_question() itself
        services/destination_resolver.py  resolve(), called only from answer_question():164

    Matching on the IMPORT rather than on "LLMTasks(" deliberately: a call is impossible without
    one, and prose mentioning the class in a docstring is not a call site.

    When this fails, someone has added a third importer. If it is also reached only via
    answer_question, add it to the list. If it is reachable any other way — a cron job, a second
    endpoint — it can spend tokens with the switch off, and it needs its own is_llm_enabled check.
    """
    root = Path(__file__).resolve().parent.parent / "app"
    importer = re.compile(r"^\s*from\s+app\.services\.llm_tasks\s+import\s+.*LLMTasks", re.M)

    callers = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if importer.search(path.read_text(encoding="utf-8"))
    }
    assert callers == {
        "services/ai_search.py",
        "services/destination_resolver.py",
    }, f"a new LLM call site appeared; confirm it is behind the kill switch: {callers}"


# --------------------------------------------------------------------------------------
# what the user gets
# --------------------------------------------------------------------------------------


def test_off_refuses_without_calling_the_llm():
    """The guarantee: a refused question costs nothing."""
    with patch("app.api.ai_search.is_llm_enabled", return_value=False), patch(
        "app.api.ai_search.record_event"
    ), patch("app.api.ai_search.answer_question") as never_called:
        r = TestClient(app).post("/api/v1/ai-search", json={"question": "how punctual is El Al?"})

    body = r.json()
    assert body["refused"] is True
    assert body["reason"] == "llm_off"
    assert body["rows"] == [] and body["columns"] == []
    never_called.assert_not_called()


def test_off_does_not_spend_the_users_daily_quota():
    """
    The switch sits above the cap, not below it.

    Below it, a visitor who asks three questions while the feature is off comes back after it is
    switched on with seven left instead of ten -- charged for answers they never received.
    """
    with patch("app.api.ai_search.is_llm_enabled", return_value=False), patch(
        "app.api.ai_search.record_event"
    ), patch("app.api.ai_search.check_and_increment_user") as counter, patch(
        "app.api.ai_search.is_over_budget"
    ) as budget:
        TestClient(app).post("/api/v1/ai-search", json={"question": "anything"})

    counter.assert_not_called()
    budget.assert_not_called()  # no DB work at all on a switched-off request


@pytest.mark.parametrize("question, lang", [("how punctual is El Al?", "en"), ("כמה אל על מדייקת?", "he")])
def test_off_says_so_in_the_askers_language(question, lang):
    """
    An off switch explains itself. It does not hide behind "I have no data".

    The generic wording tells a visitor the product is empty; this one tells them it is temporary
    and points at the parts of the site that still work.
    """
    with patch("app.api.ai_search.is_llm_enabled", return_value=False), patch(
        "app.api.ai_search.record_event"
    ), patch("app.api.ai_search.answer_question"):
        body = TestClient(app).post("/api/v1/ai-search", json={"question": question}).json()

    assert body["answer"] == off_text(lang)
    assert body["answer"] not in _GENERIC.values(), "off must not read as 'we have no data'"


def test_off_is_recorded_for_the_dashboard():
    """A blocked question is traffic worth seeing, with the words the user actually read."""
    with patch("app.api.ai_search.is_llm_enabled", return_value=False), patch(
        "app.api.ai_search.record_event"
    ) as rec, patch("app.api.ai_search.answer_question"):
        TestClient(app).post("/api/v1/ai-search", json={"question": "anything"})

    kwargs = rec.call_args.kwargs
    assert kwargs["refused"] is True and kwargs["reason"] == "llm_off"
    assert kwargs["tokens"] == 0
    assert kwargs["answer"] == off_text("en")


def test_an_empty_question_while_off_still_reads_as_off():
    """
    Order matters at the top of the ladder too.

    Below the length check, a blank or over-long question sent while the feature is off comes back
    as off_domain -- "I don't have data that answers that" -- which is the wrong explanation for
    the state the system is actually in.
    """
    with patch("app.api.ai_search.is_llm_enabled", return_value=False), patch(
        "app.api.ai_search.record_event"
    ), patch("app.api.ai_search.answer_question"):
        client = TestClient(app)
        blank = client.post("/api/v1/ai-search", json={"question": "   "}).json()
        huge = client.post(
            "/api/v1/ai-search", json={"question": "x" * (settings.ai_max_question_chars + 1)}
        ).json()

    assert blank["reason"] == "llm_off"
    assert huge["reason"] == "llm_off"


def test_on_is_the_unchanged_path():
    """The switch must be invisible when it is on."""
    stub = AISearchResponse(
        answer="El Al was on time 36.0% of the time.", rows=[{"a": 1}], columns=["a"], source="handler"
    )
    with patch("app.api.ai_search.is_llm_enabled", return_value=True), patch(
        "app.api.ai_search.is_over_budget", return_value=False
    ), patch("app.api.ai_search.check_and_increment_user", return_value=(True, 3)), patch(
        "app.api.ai_search.record_event"
    ), patch("app.api.ai_search.record_tokens"), patch(
        "app.api.ai_search.answer_question", return_value=(stub, 120)
    ):
        body = TestClient(app).post(
            "/api/v1/ai-search", json={"question": "how punctual is El Al?"}
        ).json()

    assert body["refused"] is False
    assert body["answer"] == "El Al was on time 36.0% of the time."


def test_switching_off_leaves_the_rest_of_the_site_alone():
    """Blast radius is the AI path. The flight data is not behind this switch."""
    with patch("app.api.ai_search.is_llm_enabled", return_value=False):
        assert TestClient(app).get("/health").status_code == 200


# --------------------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers, why",
    [
        ({}, "no header at all"),
        ({"Authorization": "Bearer wrong-token"}, "a guessed token"),
        ({"Authorization": ADMIN_TOKEN}, "the raw token without the Bearer scheme"),
        ({"Authorization": "Bearer "}, "an empty token"),
    ],
)
def test_a_stranger_cannot_flip_the_switch(headers, why):
    """
    The toggle is a public-internet write. Anyone who can flip it can disable the product, or
    re-enable it and spend the token budget.
    """
    with patch.object(settings, "admin_token", ADMIN_TOKEN), patch(
        "app.api.admin.set_llm_enabled"
    ) as never_called:
        r = TestClient(app).post(ENDPOINT, json={"enabled": False}, headers=headers)

    assert r.status_code == 401, why
    never_called.assert_not_called()


def test_nobody_can_flip_the_switch_when_no_token_is_configured():
    """Fail closed, exactly as the existing admin endpoints do: unset ADMIN_TOKEN denies everyone."""
    with patch.object(settings, "admin_token", ""), patch("app.api.admin.set_llm_enabled") as never:
        r = TestClient(app).post(ENDPOINT, json={"enabled": False}, headers=_admin(""))

    assert r.status_code == 401
    never.assert_not_called()


def test_the_admin_can_flip_it_and_read_it_back():
    """The round trip the dashboard button makes."""
    state = {"enabled": True}

    def _set(db, enabled, note=None):
        state["enabled"] = enabled
        return {"enabled": enabled, "updated_at": "2026-07-26T14:32:11+00:00", "note": note}

    with patch.object(settings, "admin_token", ADMIN_TOKEN), patch(
        "app.api.admin.set_llm_enabled", side_effect=_set
    ), patch("app.api.admin.get_llm_flag", side_effect=lambda db: {**state, "updated_at": None, "note": None}):
        client = TestClient(app)
        off = client.post(ENDPOINT, json={"enabled": False}, headers=_admin())
        read_back = client.get(ENDPOINT, headers=_admin())

    assert off.status_code == 200 and off.json()["enabled"] is False
    assert read_back.json()["enabled"] is False


def test_the_button_sends_the_state_it_wants_not_a_flip():
    """
    Idempotent by design: two admins on the dashboard at once, or one double-click, must not race
    into the state neither of them chose. Posting enabled=false twice leaves it false.
    """
    seen = []

    with patch.object(settings, "admin_token", ADMIN_TOKEN), patch(
        "app.api.admin.set_llm_enabled",
        side_effect=lambda db, enabled, note=None: seen.append(enabled)
        or {"enabled": enabled, "updated_at": None, "note": note},
    ):
        client = TestClient(app)
        client.post(ENDPOINT, json={"enabled": False}, headers=_admin())
        client.post(ENDPOINT, json={"enabled": False}, headers=_admin())

    assert seen == [False, False]


def test_no_admin_response_ever_contains_the_token():
    """
    The dashboard holds the token; the API must never hand it back out.

    Cheap to get wrong -- an error message that echoes what was expected, or a state object built
    from `settings`, would leak the one secret that guards every admin endpoint.
    """
    with patch.object(settings, "admin_token", ADMIN_TOKEN), patch(
        "app.api.admin.get_llm_flag", return_value={"enabled": True, "updated_at": None, "note": None}
    ):
        client = TestClient(app)
        responses = [
            client.get(ENDPOINT, headers=_admin()),
            client.get(ENDPOINT, headers=_admin("wrong")),
            client.post(ENDPOINT, json={"enabled": False}, headers=_admin("wrong")),
            client.post(ENDPOINT, json={"enabled": "not-a-bool"}, headers=_admin()),
        ]

    for r in responses:
        assert ADMIN_TOKEN not in r.text
        assert ADMIN_TOKEN not in str(dict(r.headers))
