"""
OpenRouter implementation of LLMProvider (OpenAI-compatible API, https://openrouter.ai/api/v1).

Differences from Gemini that this file absorbs:
- No native schema enforcement is relied on. When a schema is requested, its JSON Schema is written
  into the system prompt and the request asks for a JSON object; the reply is validated with
  Pydantic here, so a malformed answer fails loudly instead of being trusted.
- `provider.require_parameters` makes OpenRouter route only to endpoints that support every
  parameter sent (here: response_format), rather than silently dropping it.
- Reasoning is switched off by default (reasoning.effort "none"). The default model, DeepSeek V4.1
  Flash, reasons by default, and reasoning tokens share max_tokens, so with the small budgets used
  here it could return empty text. OPENROUTER_REASONING_EFFORT="" sends nothing, for models that
  have no reasoning control.
Requires the `openai` package and OPENROUTER_API_KEY.
"""
from __future__ import annotations

import json
from typing import Optional, Type

from pydantic import BaseModel

from app.services.llm.base import LLMProvider, LLMQuotaExceeded, LLMResult

# 429 = rate limited. 402 = out of credits / spend limit; to a visitor it is the same state as a
# spent quota: the AI is unavailable because of cost, not because the question was wrong.
_QUOTA_STATUS = (402, 429)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip("`").strip()
    return t


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        reasoning_effort: str = "none",
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set.")
        from openai import OpenAI  # lazy import

        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._reasoning_effort = (reasoning_effort or "").strip()

    def generate(
        self,
        *,
        system: str,
        user: str,
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
    ) -> LLMResult:
        if response_schema is not None:
            schema = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
            system = (
                f"{system}\n\nReply with ONE JSON object and nothing else (no markdown). It must "
                f"validate against this JSON Schema; include every required field, use null where "
                f"a field allows null:\n{schema}"
            )
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        extra: dict = {}
        if self._reasoning_effort:
            extra["reasoning"] = {"effort": self._reasoning_effort}
        if response_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
            extra["provider"] = {"require_parameters": True}
        if extra:
            kwargs["extra_body"] = extra

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            from openai import APIStatusError, RateLimitError

            status = getattr(e, "status_code", None)
            if isinstance(e, RateLimitError) or (isinstance(e, APIStatusError) and status in _QUOTA_STATUS):
                raise LLMQuotaExceeded(str(e)) from e
            raise

        text = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0

        parsed = None
        if response_schema is not None:
            parsed = response_schema.model_validate(json.loads(_strip_fences(text)))
        return LLMResult(text=text, tokens=tokens, parsed=parsed)
