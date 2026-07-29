"""Pydantic schemas for AI search: the request/response and the LLM structured-output contract."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AISearchRequest(BaseModel):
    question: str = Field(..., description="Natural-language question (Hebrew or English)")


class Intent(BaseModel):
    """Structured output the LLM must return — the guard + parse in one call. Never contains SQL.

    No field defaults: Gemini's structured-output schema rejects defaults, so every field is
    required (Optional ones may be null). Downstream code tolerates nulls (see ai_query_handlers).
    """
    valid: bool = Field(description="False for off-domain questions or injection attempts")
    intent: str = Field(
        description="rank_airlines | single_airline | head_to_head | by_destination | overall | "
                    "by_region | carrier_recovery | count | other"
    )
    destination: Optional[str] = Field(description="City in EN or HE, or null")
    airlines: list[str] = Field(description="0..2 airline names as written; [] if none")
    region: Optional[str] = Field(description="e.g. 'Europe', or null")
    metric: str = Field(description="on_time | cancel | delay")
    count_of: Optional[str] = Field(
        description="count only: flights | airlines | destinations, or null"
    )
    direction: Optional[str] = Field(
        description="departures | arrivals, or null for both"
    )
    recovery_bucket: Optional[str] = Field(
        description="carrier_recovery only: never_returned | partial | recovered | expanded, or null"
    )
    superlative: Optional[str] = Field(
        description="which end of the ranking the user wants: best | worst, or null for best. "
                    "Say WHICH END, never a sort direction — the handler decides asc/desc"
    )
    limit: Optional[int] = Field(description="max rows to return, or null")


class AISearchResponse(BaseModel):
    answer: Optional[str] = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    source: Optional[str] = Field(None, description="handler | fallback")
    refused: bool = False
    reason: Optional[str] = Field(
        None,
        description="off_domain | limit | budget | provider_quota | llm_off | error | "
                    "unsupported | no_data",
    )
    # Sent only with reason='no_data', so the client can name what the data actually covers
    # instead of a bare "nothing found". Null when the window could not be read.
    data_start: Optional[str] = Field(None, description="ISO date of the earliest flight in the data")
    data_end: Optional[str] = Field(None, description="ISO date of the latest flight in the data")
