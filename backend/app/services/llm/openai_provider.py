"""
OpenAI implementation of LLMProvider — demonstrates that adding a provider is ONE file.

Not wired in unless LLM_PROVIDER=openai. Requires `pip install openai` and OPENAI_API_KEY.
The google-genai path is unaffected (this module is imported lazily by the factory).
"""
from __future__ import annotations

import json
from typing import Optional, Type

from pydantic import BaseModel

from app.services.llm.base import LLMProvider, LLMQuotaExceeded, LLMResult


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        from openai import OpenAI  # lazy import

        self._client = OpenAI(api_key=api_key)
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
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if response_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # Same translation the Gemini provider does, in this vendor's vocabulary: a spent
            # quota and a rate limit both arrive as RateLimitError / HTTP 429.
            from openai import RateLimitError

            if isinstance(e, RateLimitError) or getattr(e, "status_code", None) == 429:
                raise LLMQuotaExceeded(str(e)) from e
            raise
        text = (resp.choices[0].message.content or "").strip()
        tokens = int(getattr(resp, "usage", None).total_tokens) if getattr(resp, "usage", None) else 0

        parsed = None
        if response_schema is not None:
            parsed = response_schema.model_validate(json.loads(text))
        return LLMResult(text=text, tokens=tokens, parsed=parsed)
