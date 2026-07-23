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
    answer, t = client.format_answer(question, rows)
    tokens += t
    return AISearchResponse(answer=answer, rows=rows, columns=columns, source=source), tokens
