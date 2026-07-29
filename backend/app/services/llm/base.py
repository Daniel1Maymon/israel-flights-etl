"""
LLM provider abstraction — the seam that makes AI search provider-agnostic.

Every provider implements one method: generate(). To add a provider you write ONE file
(subclass LLMProvider) and register it in the factory (services/llm/__init__.py). Nothing
else in the codebase imports a specific vendor SDK.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Type

from pydantic import BaseModel


class LLMQuotaExceeded(RuntimeError):
    """
    The provider refused the call because an account limit was reached — a spend cap, a quota or a
    rate limit — and not because anything about the request was wrong.

    Raised by the provider subclass, the only layer that can recognise its vendor's way of saying
    it (Gemini answers 429 RESOURCE_EXHAUSTED; OpenAI raises RateLimitError). It exists so the
    layers above can tell "the AI is unavailable because of cost" from "the AI broke", which are
    different states with different words for the user — see services/refusal_text.py.

    This class earned its place: a Google project spend cap surfaced as "I don't have data that
    answers that", so a working dataset read as an empty one and the only trace was a log line.
    """


@dataclass
class LLMResult:
    """Uniform result across providers."""
    text: str                          # raw text output (empty when only structured output requested)
    tokens: int                        # total tokens used, for budget metering
    parsed: Optional[BaseModel] = None # populated when response_schema was requested


class LLMProvider(ABC):
    """A minimal text-in / (text|structured)-out contract. Vendor SDKs live only in subclasses."""

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        user: str,
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
    ) -> LLMResult:
        """Run one completion. If response_schema is given, LLMResult.parsed must be populated."""
        raise NotImplementedError
