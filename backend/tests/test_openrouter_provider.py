"""
OpenRouter provider: offline tests only. The OpenAI client is replaced with a fake, so nothing here
touches the network or costs a token. They pin the three things the switch can silently break:
the request actually goes to OpenRouter, the Intent schema reaches the model, and a bad or
over-limit reply fails loudly instead of being trusted.
"""
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError, RateLimitError

from app.config import settings
from app.schemas.ai_search import Intent
from app.services.llm import get_provider
from app.services.llm.base import LLMQuotaExceeded
from app.services.llm.openrouter_provider import OpenRouterProvider

GOOD_INTENT = {
    "valid": True, "intent": "count", "destination": None, "airlines": [], "region": None,
    "metric": "on_time", "count_of": "airlines", "direction": None, "recovery_bucket": None,
    "superlative": None, "limit": None,
}


def _fill_missing(d: dict) -> dict:
    """The fixture must cover every Intent field; a new required field makes this fail loudly."""
    missing = set(Intent.model_fields) - set(d)
    assert not missing, f"update GOOD_INTENT for new Intent fields: {missing}"
    return dict(d)


class FakeCompletions:
    def __init__(self, reply=None, exc=None):
        self.reply, self.exc, self.calls = reply, exc, []

    def create(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))],
            usage=SimpleNamespace(total_tokens=123),
        )


def _provider(monkeypatch, reply=None, exc=None):
    p = OpenRouterProvider(model="vendor/model", api_key="test-key-not-real")
    fake = FakeCompletions(reply, exc)
    p._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return p, fake


def _status_error(cls, code):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(code, request=req, json={"error": {"message": "x"}})
    return cls("x", response=resp, body=None)


def test_client_points_at_openrouter(monkeypatch):
    p = OpenRouterProvider(model="m", api_key="test-key-not-real")
    assert str(p._client.base_url).startswith("https://openrouter.ai/api/v1")


def test_missing_key_fails_loudly():
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(model="m", api_key="")


def test_schema_is_sent_to_the_model(monkeypatch):
    p, fake = _provider(monkeypatch, reply=json.dumps(_fill_missing(GOOD_INTENT)))
    r = p.generate(system="SYS", user="how many airlines?", response_schema=Intent)
    call = fake.calls[0]
    system = call["messages"][0]["content"]
    assert system.startswith("SYS")
    for field in Intent.model_fields:  # every required key is spelled out for the model
        assert f'"{field}"' in system
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"provider": {"require_parameters": True}}
    assert call["model"] == "vendor/model" and call["temperature"] == 0.0
    assert isinstance(r.parsed, Intent) and r.tokens == 123


def test_fenced_json_is_accepted(monkeypatch):
    p, _ = _provider(monkeypatch, reply="```json\n" + json.dumps(_fill_missing(GOOD_INTENT)) + "\n```")
    assert isinstance(p.generate(system="s", user="u", response_schema=Intent).parsed, Intent)


def test_invalid_json_is_not_trusted(monkeypatch):
    p, _ = _provider(monkeypatch, reply="sure, here you go")
    with pytest.raises(ValueError):
        p.generate(system="s", user="u", response_schema=Intent)


def test_missing_required_field_is_rejected(monkeypatch):
    bad = _fill_missing(GOOD_INTENT)
    bad.pop("intent")
    p, _ = _provider(monkeypatch, reply=json.dumps(bad))
    with pytest.raises(Exception):
        p.generate(system="s", user="u", response_schema=Intent)


def test_plain_text_call_sends_no_json_mode(monkeypatch):
    p, fake = _provider(monkeypatch, reply="  Crete is HERAKLION  ")
    r = p.generate(system="s", user="u", max_output_tokens=32)
    assert "response_format" not in fake.calls[0] and "extra_body" not in fake.calls[0]
    assert fake.calls[0]["max_tokens"] == 32
    assert r.text == "Crete is HERAKLION" and r.parsed is None


@pytest.mark.parametrize("cls,code", [(RateLimitError, 429), (APIStatusError, 402)])
def test_limits_become_quota_exceeded(monkeypatch, cls, code):
    p, _ = _provider(monkeypatch, exc=_status_error(cls, code))
    with pytest.raises(LLMQuotaExceeded):
        p.generate(system="s", user="u")


def test_other_errors_are_not_reported_as_quota(monkeypatch):
    p, _ = _provider(monkeypatch, exc=_status_error(APIStatusError, 500))
    with pytest.raises(APIStatusError):
        p.generate(system="s", user="u")


def test_factory_key_selects_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key-not-real")
    p = get_provider()
    assert isinstance(p, OpenRouterProvider)
    assert p._model == settings.openrouter_model != "gemini-2.5-flash"  # Gemini model id never leaks over


def test_factory_without_key_keeps_configured_provider(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_provider()


def test_explicit_openrouter_without_key_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_provider()


def test_unknown_provider_still_rejected(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(ValueError):
        get_provider("nope")
