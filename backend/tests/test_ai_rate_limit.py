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

from app.api.ai_search import _client_ip
from app.config import settings
from app.main import app
from app.schemas.ai_search import AISearchResponse
from app.services.ratelimit import check_and_increment_user, make_user_key
from app.services.refusal_text import _GENERIC, limit_text


class _Req:
    """Minimal stand-in for Request: headers and the socket peer are all _client_ip reads."""

    def __init__(
        self, xff: str | None = None, peer: str | None = "203.0.113.7", **headers: str
    ) -> None:
        self.headers = {k.replace("_", "-"): v for k, v in headers.items()}
        if xff:
            self.headers["x-forwarded-for"] = xff
        self.client = type("C", (), {"host": peer})() if peer else None


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


def test_the_same_ip_is_one_identity_whatever_the_cookie_says():
    """
    The cap counts IPs. Cookies used to be mixed in, and that is exactly why it never fired: the
    cookie is SameSite=Lax across two sites, so it never came back and every request looked new.
    """
    assert make_user_key("203.0.113.7", "cookie-a") == make_user_key("203.0.113.7", "cookie-b")
    assert make_user_key("203.0.113.7", None) == make_user_key("203.0.113.7", "anything")
    assert make_user_key("203.0.113.7", "c") != make_user_key("198.51.100.4", "c")
    assert "203.0.113.7" not in make_user_key("203.0.113.7", "c")  # hashed, never stored raw


def test_without_an_ip_the_cookie_still_separates_callers():
    """No IP at all (a test client, an odd proxy) must not merge everyone into one bucket."""
    assert make_user_key(None, "cookie-a") != make_user_key(None, "cookie-b")


# Real public addresses, not the 203.0.113.x documentation range: Python's ipaddress counts the
# TEST-NET blocks as private, so using them here would test nothing.
# 5.5.5.5 plays the visitor, 152.233.13.166 the platform edge (the address that really appeared),
# 1.1.1.1 whatever a caller forged. Default TRUSTED_PROXY_HOPS is 1.
@pytest.mark.parametrize(
    "xff, expected, why",
    [
        ("5.5.5.5, 152.233.13.166", "5.5.5.5", "visitor sits one hop left of the edge"),
        ("1.1.1.1, 5.5.5.5, 152.233.13.166", "5.5.5.5", "forged entry left of the visitor ignored"),
        ("5.5.5.5", "5.5.5.5", "chain shorter than the hop count -> the only entry"),
        ("5.5.5.5, 10.0.0.8", "5.5.5.5", "internal hop, then walk left to a routable address"),
        ("not-an-ip, 5.5.5.5, 152.233.13.166", "5.5.5.5", "garbage entry ignored"),
        ("10.0.0.8", "9.9.9.9", "nothing routable -> socket peer"),
        (None, "9.9.9.9", "no header -> socket peer"),
    ],
)
def test_the_visitor_is_read_a_fixed_distance_from_the_right(xff, expected, why):
    """
    Neither end of X-Forwarded-For is the visitor.

    The left end is caller-supplied, so trusting it hands out free identities. The right end is the
    last proxy, which every visitor shares — reading that put all traffic on the platform edge's
    address and refused real users at question eleven. The browser is a fixed number of hops from
    the right: one per proxy in front of the app.
    """
    assert _client_ip(_Req(xff, peer="9.9.9.9")) == expected, why


def test_an_edge_supplied_client_ip_header_wins():
    """A CDN that states the address it saw is better evidence than counting hops ourselves."""
    req = _Req("1.1.1.1, 152.233.13.166", peer="9.9.9.9", cf_connecting_ip="5.5.5.5")
    assert _client_ip(req) == "5.5.5.5"
    # ...but not when it holds something unroutable — fall back to the chain rather than trust it.
    assert _client_ip(_Req("5.5.5.5, 152.233.13.166", x_real_ip="10.0.0.1")) == "5.5.5.5"


def test_hop_count_is_configurable():
    """Two proxies in front means the visitor is two from the right, not one."""
    chain = "1.1.1.1, 5.5.5.5, 152.233.13.166, 152.233.13.167"
    with patch.object(settings, "trusted_proxy_hops", 2):
        assert _client_ip(_Req(chain)) == "5.5.5.5"
    with patch.object(settings, "trusted_proxy_hops", 1):
        assert _client_ip(_Req(chain)) == "152.233.13.166"  # what one-hop-too-few looks like


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
    [("how punctual is El Al?", limit_text("en")), ("כמה אל על מדייקת?", limit_text("he"))],
)
def test_a_capped_user_is_told_they_are_capped(question, expected):
    """
    The cap says so, in the asker's language — it does not hide behind the generic refusal.

    Under the generic wording ("I don't have data that answers that") a capped visitor concludes
    the product is empty and does not return. The data exists; they get it tomorrow. This is the
    one refusal whose next step differs, and the only one with its own words.
    """
    with patch("app.api.ai_search.is_llm_enabled", return_value=True), patch(
        "app.api.ai_search.is_over_budget", return_value=False
    ), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(False, 11)
    ), patch("app.api.ai_search.record_event"), patch(
        "app.api.ai_search.answer_question"
    ) as never_called:
        r = TestClient(app).post("/api/v1/ai-search", json={"question": question}).json()

    assert r["refused"] is True
    assert r["reason"] == "limit"
    assert r["answer"] == expected
    assert r["answer"] not in _GENERIC.values(), "the cap must not read as 'we have no data'"
    assert r["rows"] == [] and r["columns"] == []
    never_called.assert_not_called()  # no LLM tokens spent on a capped user


def test_the_cap_notice_quotes_the_configured_number():
    """A hard-coded number would go stale the first time an environment overrides the setting."""
    for lang in ("en", "he"):
        assert str(settings.ai_daily_limit_per_user) in limit_text(lang)


def test_the_capped_request_is_still_recorded():
    """A blocked question is traffic worth seeing in the dashboard, with the text the user got."""
    with patch("app.api.ai_search.is_llm_enabled", return_value=True), patch(
        "app.api.ai_search.is_over_budget", return_value=False
    ), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(False, 11)
    ), patch("app.api.ai_search.record_event") as rec:
        TestClient(app).post("/api/v1/ai-search", json={"question": "anything"})

    kwargs = rec.call_args.kwargs
    assert kwargs["refused"] is True and kwargs["reason"] == "limit"
    assert kwargs["answer"] == limit_text("en")
    assert kwargs["tokens"] == 0


def test_budget_kill_switch_also_answers_in_words():
    """Same contract for the global budget refusal — no path returns a null answer."""
    with patch("app.api.ai_search.is_llm_enabled", return_value=True), patch(
        "app.api.ai_search.is_over_budget", return_value=True
    ), patch("app.api.ai_search.record_event"):
        r = TestClient(app).post("/api/v1/ai-search", json={"question": "hello"}).json()

    assert (r["refused"], r["reason"], r["answer"]) == (True, "budget", _GENERIC["en"])


def test_an_answered_question_keeps_its_own_words():
    """The generic text must not leak onto a real answer."""
    stub = AISearchResponse(answer="El Al was on time 36.0% of the time.", rows=[{"a": 1}],
                            columns=["a"], source="handler")
    with patch("app.api.ai_search.is_llm_enabled", return_value=True), patch(
        "app.api.ai_search.is_over_budget", return_value=False
    ), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(True, 3)
    ), patch("app.api.ai_search.record_event"), patch(
        "app.api.ai_search.record_tokens"  # the allowed path banks tokens; needs a writable DB
    ), patch("app.api.ai_search.answer_question", return_value=(stub, 120)):
        r = TestClient(app).post("/api/v1/ai-search", json={"question": "how punctual is El Al?"}).json()

    assert r["refused"] is False
    assert r["answer"] == "El Al was on time 36.0% of the time."
