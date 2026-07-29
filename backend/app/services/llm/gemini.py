"""Gemini implementation of LLMProvider. The only file that imports the google-genai SDK."""
from __future__ import annotations

import json
from typing import Optional, Type

from pydantic import BaseModel

from app.services.llm.base import LLMProvider, LLMQuotaExceeded, LLMResult


def _quota_message(exc: Exception) -> Optional[str]:
    """
    The provider's own words if this is a limit refusal, else None.

    Gemini says 429 RESOURCE_EXHAUSTED for all of them — the project spend cap, the free-tier
    quota, and per-minute rate limiting — and the three are one situation to a visitor: not now,
    try later. Matched on APIError rather than on any object carrying a `code`, so an unrelated
    exception that happens to have one is not mistaken for a billing problem.
    """
    from google.genai.errors import APIError

    if not isinstance(exc, APIError):
        return None
    if exc.code == 429 or (exc.status or "").upper() == "RESOURCE_EXHAUSTED":
        return exc.message or str(exc)
    return None


class GeminiProvider(LLMProvider):
    def __init__(self, model: str, api_key: str) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        from google import genai  # lazy: app boots without the SDK/key

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(
        self,
        *,
        system: str,
        user: str,
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
    ) -> LLMResult:
        config: dict = {
            "system_instruction": system,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            # 2.5+ Flash "thinking" models otherwise spend the token budget on hidden reasoning
            # and truncate the answer; this task doesn't need it (cheaper + faster too).
            "thinking_config": {"thinking_budget": 0},
        }
        if response_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = response_schema

        try:
            resp = self._client.models.generate_content(
                model=self._model, contents=user, config=config
            )
        except Exception as e:
            # Translated here because this is the only file that may know what a Gemini error is.
            # Everything above sees the provider-agnostic LLMQuotaExceeded (see llm/base.py).
            message = _quota_message(e)
            if message is None:
                raise
            raise LLMQuotaExceeded(message) from e

        meta = getattr(resp, "usage_metadata", None)
        tokens = int(getattr(meta, "total_token_count", 0) or 0) if meta else 0

        parsed = None
        if response_schema is not None:
            p = getattr(resp, "parsed", None)
            parsed = p if isinstance(p, response_schema) else response_schema.model_validate(
                json.loads(resp.text)
            )
        return LLMResult(text=(resp.text or "").strip(), tokens=tokens, parsed=parsed)
