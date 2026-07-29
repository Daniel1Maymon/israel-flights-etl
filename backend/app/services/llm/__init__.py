"""LLM provider factory — pick the provider by config, so switching is env-only."""
from __future__ import annotations

from app.config import settings
from app.services.llm.base import LLMProvider, LLMQuotaExceeded, LLMResult

__all__ = ["LLMProvider", "LLMQuotaExceeded", "LLMResult", "get_provider"]


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the configured LLM provider. Switch via LLM_PROVIDER / LLM_MODEL — no code change."""
    name = (name or settings.llm_provider or "gemini").lower()

    if name == "gemini":
        from app.services.llm.gemini import GeminiProvider
        return GeminiProvider(model=settings.llm_model, api_key=settings.gemini_api_key)

    if name == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(model=settings.llm_model, api_key=settings.openai_api_key)

    raise ValueError(f"unknown LLM provider: {name!r}")
