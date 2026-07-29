"""
Telling a cost outage apart from a fault, and both apart from "we have no data".

This exists because of a production incident with no visible symptom. The Google project's
monthly spend cap was reached, every Gemini call came back 429 RESOURCE_EXHAUSTED, the exception
landed in the endpoint's catch-all as reason='error', and the site answered every question —
including ones it answers well — with "אין לי נתונים שעונים על השאלה הזו". Nothing was wrong
with the data. Users were told the product was empty; the only record of the truth was one log
line.

Three seams have to hold for that to be impossible, and each is pinned below.

  the provider   recognises its vendor's limit refusal and raises the shared LLMQuotaExceeded
  the endpoint   catches it ABOVE the catch-all, so a cap is never filed as a fault
  the words      a ceiling, a fault and missing data read as three different things

The resolver gets its own section: it swallows exceptions by design (an outage there must not
become a wrong answer) and that swallow used to eat this one too, turning a billing ceiling into
"no flights to Barcelona".
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.destination_resolver import Vocabulary, resolve
from app.services.llm import LLMQuotaExceeded
from app.services.llm.gemini import GeminiProvider
from app.services.refusal_text import (
    _GENERIC,
    budget_text,
    error_text,
    limit_text,
    off_text,
    refusal_answer,
)

# The real message Gemini returned when the cap was hit.
SPEND_CAP = "Your project has exceeded its monthly spending cap."


def _api_error(code: int, status: str, message: str):
    """A genuine google-genai APIError, built the way the SDK builds one from a response body."""
    from google.genai.errors import ClientError

    return ClientError(code, {"error": {"code": code, "message": message, "status": status}})


class _RaisingClient:
    """Stands in for genai.Client: every generate_content raises the error under test."""

    def __init__(self, exc: Exception) -> None:
        self.models = self
        self._exc = exc

    def generate_content(self, **_kw):
        raise self._exc


def _gemini(exc: Exception) -> GeminiProvider:
    p = GeminiProvider("gemini-2.5-flash", "test-key")  # no network on construction
    p._client = _RaisingClient(exc)
    return p


def _post(question: str = "how punctual is El Al?", **overrides):
    """Drive the endpoint with every guard open, so only the orchestrator's outcome is under test."""
    behaviour = {"side_effect": RuntimeError("boom")}
    behaviour.update(overrides)
    with patch("app.api.ai_search.is_llm_enabled", return_value=True), patch(
        "app.api.ai_search.is_over_budget", return_value=False
    ), patch(
        "app.api.ai_search.check_and_increment_user", return_value=(True, 1)
    ), patch("app.api.ai_search.record_event") as rec, patch(
        "app.api.ai_search.record_tokens"
    ), patch("app.api.ai_search.answer_question", **behaviour):
        body = TestClient(app).post("/api/v1/ai-search", json={"question": question}).json()
    return body, rec


# --------------------------------------------------------------------------------------
# the provider: only this layer knows what its vendor's "you are out of quota" looks like
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code, status, why",
    [
        (429, "RESOURCE_EXHAUSTED", "the spend cap that caused the incident"),
        (429, "", "a 429 with no status is still a limit refusal"),
        (400, "RESOURCE_EXHAUSTED", "status alone is enough; the code may vary"),
    ],
)
def test_gemini_reports_a_limit_refusal_as_a_quota_error(code, status, why):
    with pytest.raises(LLMQuotaExceeded) as caught:
        _gemini(_api_error(code, status, SPEND_CAP)).generate(system="s", user="u")

    # The provider's own sentence survives: it names WHICH ceiling, which is what an operator
    # needs to know to clear it. A message of our own invention could not say that.
    assert SPEND_CAP in str(caught.value), why


@pytest.mark.parametrize(
    "exc, why",
    [
        (_api_error(400, "INVALID_ARGUMENT", "bad request"), "a broken request is not a cap"),
        (_api_error(500, "INTERNAL", "server error"), "a provider outage is not a cap"),
        (ValueError("code = 429"), "not an APIError; the digits are a coincidence"),
    ],
)
def test_gemini_does_not_call_every_failure_a_quota_error(exc, why):
    """
    Over-matching would be the same bug pointing the other way: a genuine fault reported to the
    user as "we hit our token limit" sends them away to wait for a limit that will never reset.
    """
    with pytest.raises(Exception) as caught:
        _gemini(exc).generate(system="s", user="u")

    assert not isinstance(caught.value, LLMQuotaExceeded), why


# --------------------------------------------------------------------------------------
# the endpoint: a ceiling is not a fault
# --------------------------------------------------------------------------------------


def test_a_spent_quota_is_refused_as_a_quota_and_not_as_a_fault():
    body, _ = _post(side_effect=LLMQuotaExceeded(SPEND_CAP))

    assert body["refused"] is True
    assert body["reason"] == "provider_quota"
    assert body["answer"] == budget_text("en")
    assert body["answer"] not in _GENERIC.values(), "a cap must never read as 'we have no data'"


def test_a_real_fault_is_still_refused_as_a_fault():
    """The catch-all keeps its job; only the quota case was carved out of it."""
    body, _ = _post(side_effect=RuntimeError("boom"))

    assert (body["refused"], body["reason"]) == (True, "error")
    assert body["answer"] == error_text("en")
    assert body["answer"] not in _GENERIC.values()


@pytest.mark.parametrize(
    "question, lang", [("how punctual is El Al?", "en"), ("כמה אל על מדייקת?", "he")]
)
def test_both_outages_speak_the_askers_language(question, lang):
    quota, _ = _post(question, side_effect=LLMQuotaExceeded(SPEND_CAP))
    fault, _ = _post(question, side_effect=RuntimeError("boom"))

    assert quota["answer"] == budget_text(lang)
    assert fault["answer"] == error_text(lang)


def test_neither_outage_leaks_the_providers_message_to_the_user():
    """
    The vendor's sentence belongs in the log and on the dashboard, not on the page. It names our
    provider, our project's billing state and a Google console URL — none of it the visitor's
    business, and the first two are internals we do not publish anywhere else.
    """
    body, _ = _post(side_effect=LLMQuotaExceeded(f"{SPEND_CAP} See https://ai.studio/spend"))

    for leak in ("spend", "cap", "Google", "ai.studio", "429", "quota", "project"):
        assert leak.lower() not in body["answer"].lower()


def test_a_quota_outage_is_recorded_for_the_dashboard():
    """
    'Why did traffic stop answering' has to be answerable after the fact, and reason is the only
    field that can answer it — every refusal carries rows=[] and tokens=0 alike.
    """
    _, rec = _post(side_effect=LLMQuotaExceeded(SPEND_CAP))

    kwargs = rec.call_args.kwargs
    assert kwargs["refused"] is True
    assert kwargs["reason"] == "provider_quota"
    assert kwargs["answer"] == budget_text("en")  # what the user actually read
    assert kwargs["tokens"] == 0  # the call was refused; nothing was spent


# --------------------------------------------------------------------------------------
# the resolver: its deliberate swallow must not eat this
# --------------------------------------------------------------------------------------


def _vocab() -> Vocabulary:
    return Vocabulary(cities=["BARCELONA"], countries=["SPAIN"],
                      aliases={"barcelona": ("city", "BARCELONA"), "spain": ("country", "SPAIN")})


def test_a_quota_error_during_resolution_is_not_reported_as_missing_data():
    """
    The exact shape of the bug, one layer down. `resolve` returning None makes the caller answer
    _no_data — a claim about the DATA — and a spent quota is no evidence for it. A place the
    dataset covers would be reported as absent because a billing ceiling was reached.
    """
    def out_of_quota(_place, _candidates):
        raise LLMQuotaExceeded(SPEND_CAP)

    with pytest.raises(LLMQuotaExceeded):
        resolve("crete", _vocab(), ask_llm=out_of_quota)


def test_an_ordinary_resolver_outage_still_refuses_quietly():
    """The swallow is still right for everything else: unresolved means refuse, never guess."""
    def broken(_place, _candidates):
        raise RuntimeError("timeout")

    assert resolve("crete", _vocab(), ask_llm=broken) == (None, 0)


# --------------------------------------------------------------------------------------
# the words themselves
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "he"])
def test_every_system_refusal_says_something_different(lang):
    """
    Five states, five sentences. Any two that collapse into one string put a user back where this
    started: reading a message that describes a different system state than the one they hit.
    """
    texts = {
        "limit": limit_text(lang),
        "llm_off": off_text(lang),
        "budget": budget_text(lang),
        "error": error_text(lang),
        "generic": _GENERIC[lang],
    }
    assert len(set(texts.values())) == len(texts), texts


@pytest.mark.parametrize("lang", ["en", "he"])
def test_an_outage_points_at_what_still_works(lang):
    """
    Both outage messages have a job beyond being accurate: keep the visitor on the site. The rest
    of the product is untouched when the LLM is unavailable, so both name where to go instead.
    """
    for text in (budget_text(lang), error_text(lang)):
        assert ("חיפוש היעדים" if lang == "he" else "destination search") in text


@pytest.mark.parametrize(
    "reason", ["off_domain", "unsupported", "no_data", None, "something_new"]
)
def test_question_shaped_refusals_keep_the_generic_wording(reason):
    """
    The carve-outs are exactly the system states. A refusal about the QUESTION — and any reason
    added later, which lands on the default — still gets the one sentence, because "I don't have
    data that answers that" is true of those and gives the user the same next step.
    """
    assert refusal_answer(reason, "how punctual is El Al?") == _GENERIC["en"]


def test_our_ceiling_and_the_providers_read_the_same_to_a_visitor():
    """
    One text for two reasons, on purpose. Whether we throttled ourselves or Google did is our
    problem; the visitor's next step is identical. `reason` is what keeps them apart, and it keeps
    them apart where the distinction is actionable — the dashboard.
    """
    question = "how punctual is El Al?"
    assert refusal_answer("budget", question) == refusal_answer("provider_quota", question)
