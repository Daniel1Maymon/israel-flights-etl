"""
The per-user daily cap: where it trips, and what the user is told when it does.

Two things are pinned here. The arithmetic — the Nth question is allowed and the N+1th is not,
which is off-by-one bait (`count` is the value AFTER the increment). And the reply — an over-limit
user gets the same generic answer as any other refusal, never a null, because the product has
exactly two things it may show: an answer from the data, or that one string.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas.ai_search import AISearchResponse
from app.services.ratelimit import check_and_increment_user
from app.services.refusal_text import _GENERIC


class _FakeSession:
    """Stands in for the writable Session: returns the post-increment count ratelimit expects."""

    def __init__(self, count_after: int) -> None:
        self._count = count_after

    def execute(self, *_a, **_kw):
        outer = self

        class _R:
            def scalar_one(self):
                return outer._count

        return _R()

    def commit(self) -> None:
        pass


@pytest.mark.parametrize(
    "count_after, allowed",
    [(1, True), (9, True), (10, True), (11, False), (50, False)],
)
def test_the_cap_trips_on_the_question_after_the_limit(count_after, allowed):
    """count is post-increment, so question number 10 is the last one allowed."""
    assert settings.ai_daily_limit_per_user == 10
    ok, n = check_and_increment_user(_FakeSession(count_after), "user-key")
    assert (ok, n) == (allowed, count_after)


@pytest.mark.parametrize(
    "question, expected",
    [("how punctual is El Al?", _GENERIC["en"]), ("כמה אל על מדייקת?", _GENERIC["he"])],
)
def test_over_limit_user_is_told_something(question, expected):
    """
    The refusal carries text — in the asker's language — and it is the generic one.

    A limit refusal used to have its own wording. It doesn't any more: the user sees one string for
    every refusal, and `reason` keeps the distinction for analytics. This test exists because that
    collapse is easy to undo by accident.
    """
    with patch("app.api.ai_search.is_over_budget", return_value=False), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(False, 11)
    ), patch("app.api.ai_search.record_event"), patch(
        "app.api.ai_search.answer_question"
    ) as never_called:
        r = TestClient(app).post("/api/v1/ai-search", json={"question": question}).json()

    assert r["refused"] is True
    assert r["reason"] == "limit"
    assert r["answer"] == expected
    assert r["rows"] == [] and r["columns"] == []
    never_called.assert_not_called()  # no LLM tokens spent on a capped user


def test_the_capped_request_is_still_recorded():
    """A blocked question is traffic worth seeing in the dashboard, with the text the user got."""
    with patch("app.api.ai_search.is_over_budget", return_value=False), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(False, 11)
    ), patch("app.api.ai_search.record_event") as rec:
        TestClient(app).post("/api/v1/ai-search", json={"question": "anything"})

    kwargs = rec.call_args.kwargs
    assert kwargs["refused"] is True and kwargs["reason"] == "limit"
    assert kwargs["answer"] == _GENERIC["en"]
    assert kwargs["tokens"] == 0


def test_budget_kill_switch_also_answers_in_words():
    """Same contract for the global budget refusal — no path returns a null answer."""
    with patch("app.api.ai_search.is_over_budget", return_value=True), patch(
        "app.api.ai_search.record_event"
    ):
        r = TestClient(app).post("/api/v1/ai-search", json={"question": "hello"}).json()

    assert (r["refused"], r["reason"], r["answer"]) == (True, "budget", _GENERIC["en"])


def test_an_answered_question_keeps_its_own_words():
    """The generic text must not leak onto a real answer."""
    stub = AISearchResponse(answer="El Al was on time 36.0% of the time.", rows=[{"a": 1}],
                            columns=["a"], source="handler")
    with patch("app.api.ai_search.is_over_budget", return_value=False), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(True, 3)
    ), patch("app.api.ai_search.record_event"), patch(
        "app.api.ai_search.record_tokens"  # the allowed path banks tokens; needs a writable DB
    ), patch("app.api.ai_search.answer_question", return_value=(stub, 120)):
        r = TestClient(app).post("/api/v1/ai-search", json={"question": "how punctual is El Al?"}).json()

    assert r["refused"] is False
    assert r["answer"] == "El Al was on time 36.0% of the time."
