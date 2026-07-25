"""
ai_search.py — the stateless orchestrator: interpret → (query handler | guarded fallback) → format.

Single-shot, no memory. This thin seam is the ONLY place statefulness would be added later
(LangGraph swap); the guard/query-handler/DB/format layers below it stay unchanged.
Returns (AISearchResponse, tokens_used) so the endpoint can meter the budget.
"""
from __future__ import annotations

import structlog

from app.config import settings
from app.schemas.ai_search import AISearchResponse
from app.services.ai_query_handlers import NoQueryHandlerMatch, run_query_handler
from app.services.ai_db import run_readonly
from app.services.llm_tasks import LLMTasks
from app.services.sql_guard import SqlGuardError, validate_and_prepare

logger = structlog.get_logger()

# Every column on the flights table. A result key matching any of these is a raw
# database column name and must never reach the client as-is.
_REAL_COLUMNS = {
    "flight_id", "airline_code", "flight_number", "direction", "location_iata",
    "location_en", "location_he", "location_city_en", "country_en", "country_he",
    "airline_name", "scheduled_time", "actual_time", "delay_minutes", "terminal",
    "checkin_counters", "checkin_zone", "status_en", "status_he",
    "scrape_timestamp", "raw_s3_path",
}

# Columns that must never be returned in any form -- no label exists for them because
# they should never be queried.
_INTERNAL_COLUMNS = {
    "raw_s3_path", "scrape_timestamp", "checkin_counters", "checkin_zone",
    "flight_id", "location_iata", "country_he", "status_he", "flight_number",
}

# Presentation labels for everything the AI path may return, covering both real columns
# and the aliases the query handlers emit. The client sees these; it never sees the
# column names behind them.
_PUBLIC_LABELS = {
    # No label may round-trip back to a real column name (lowercased, spaces -> "_"),
    # or the header still hands over the identifier. Enforced by
    # test_no_label_round_trips_to_a_column_name.
    "airline_name": "Airline",
    "airline_code": "IATA Code",
    "direction": "Arrival / Departure",
    "location_en": "Destination",
    "location_he": "יעד",
    "location_city_en": "City",
    "country_en": "Country",
    "scheduled_time": "Scheduled",
    "actual_time": "Actual",
    "delay_minutes": "Delay (minutes)",
    "status_en": "Status",
    "terminal": "Terminal No.",
    # handler-defined aliases
    "destination": "Destination",
    "total_flights": "Total Flights",
    "on_time_pct": "On-Time %",
    "cancel_pct": "Cancelled %",
    "avg_delay_minutes": "Avg Delay (minutes)",
}


def _public_label(name: str) -> str | None:
    """
    Map a result key to its client-facing label, or None if it must be dropped.

    Three cases, in order:
      1. known column or handler alias -> its label
      2. an unmapped REAL column       -> dropped (fail closed; a column added to the
                                          table must not become visible by default)
      3. anything else                 -> a query-defined alias, prettified
    """
    key = (name or "").strip().lower()
    if key in _INTERNAL_COLUMNS:
        return None
    if key in _PUBLIC_LABELS:
        return _PUBLIC_LABELS[key]
    if key in _REAL_COLUMNS:
        return None
    return name.replace("_", " ").strip().title()


def _to_public_columns(
    columns: list[str], rows: list[dict]
) -> tuple[list[str], list[dict]]:
    """
    Relabel results before they leave the service.

    The LLM is told to select a 12-column subset and does so faithfully -- but those 12
    are real column names, so returning them verbatim publishes the table's structure
    just as surely as SELECT * would. Renaming at the boundary is what actually decouples
    the answer from the schema; the prompt and sql_guard only decide which columns may be
    read, not what the client is shown.

    Applied to both the handler and fallback paths, and before format_answer, so the LLM
    writing the prose answer never sees a raw column name either.
    """
    mapping: dict[str, str] = {}
    dropped: list[str] = []
    for col in columns:
        label = _public_label(col)
        if label is None:
            dropped.append(col)
        else:
            mapping[col] = label

    if dropped:
        logger.warning("dropped non-public columns from AI result", columns=dropped)

    public_columns = [mapping[c] for c in columns if c in mapping]
    public_rows = [
        {mapping[k]: v for k, v in row.items() if k in mapping} for row in rows
    ]
    return public_columns, public_rows


def answer_question(question: str) -> tuple[AISearchResponse, int]:
    tokens = 0
    client = LLMTasks()  # provider chosen by config; raises if the provider's key is missing

    # 1) interpret (guard + parse in one call)
    intent, t = client.interpret(question)
    tokens += t
    if not intent.valid:
        return AISearchResponse(refused=True, reason="off_domain"), tokens

    # 2) run: reviewed query handler first, else guarded generated-SQL fallback
    try:
        columns, rows = run_query_handler(intent.model_dump())
        source = "handler"
    except NoQueryHandlerMatch:
        sql, t = client.generate_sql(question)
        tokens += t
        try:
            safe_sql = validate_and_prepare(sql, settings.ai_max_rows)
        except SqlGuardError as e:
            logger.warning("fallback sql rejected", error=str(e))
            return AISearchResponse(refused=True, reason="unsupported"), tokens
        try:
            columns, rows = run_readonly(safe_sql)
        except Exception as e:  # timeout / db error → generic
            logger.warning("fallback sql execution failed", error=str(e))
            return AISearchResponse(refused=True, reason="error"), tokens
        source = "fallback"

    # 3) format grounded in the returned rows
    # Applies to BOTH paths (handler and fallback) and runs before format_answer, so
    # raw column names are never even shown to the LLM that writes the prose answer.
    columns, rows = _to_public_columns(columns, rows)

    answer, t = client.format_answer(question, rows)
    tokens += t
    return AISearchResponse(answer=answer, rows=rows, columns=columns, source=source), tokens
