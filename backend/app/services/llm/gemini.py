"""Gemini implementation of LLMProvider. The only file that imports the google-genai SDK."""
from __future__ import annotations

import json
from typing import Optional, Type

from pydantic import BaseModel

from app.services.llm.base import LLMProvider, LLMResult


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

        resp = self._client.models.generate_content(model=self._model, contents=user, config=config)

        meta = getattr(resp, "usage_metadata", None)
        tokens = int(getattr(meta, "total_token_count", 0) or 0) if meta else 0

        parsed = None
        if response_schema is not None:
            p = getattr(resp, "parsed", None)
            parsed = p if isinstance(p, response_schema) else response_schema.model_validate(
                json.loads(resp.text)
            )
        return LLMResult(text=(resp.text or "").strip(), tokens=tokens, parsed=parsed)
