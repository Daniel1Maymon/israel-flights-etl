"""
AI Search endpoint — POST /api/v1/ai-search.

Free-text question in → grounded answer + supporting rows out. Applies the cost/abuse guards
(global budget kill-switch, per-user daily cap) before spending any LLM tokens, then delegates
to the stateless orchestrator. All failures return a generic refusal (no internals leaked).

Every request also writes one analytics event (see services/analytics.py) — best-effort, never
allowed to break the user path.
"""
from __future__ import annotations

import secrets
import time

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
from app.schemas.ai_search import AISearchRequest, AISearchResponse
from app.services.ai_search import answer_question
from app.services.analytics import record_event
from app.services.refusal_text import refusal_answer
from app.services.ratelimit import (
    check_and_increment_user,
    is_over_budget,
    make_user_key,
    record_tokens,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai-search", tags=["ai-search"])

# Table creation moved to app.main's lifespan. Doing it lazily here meant DDL ran on
# the request path, where concurrent workers deadlocked on ai_events (see schema_init).


def _client_ip(request: Request) -> str | None:
    """Real client IP: first hop of X-Forwarded-For (Railway proxies), else the socket peer."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _resolve(db: Session, question: str, user_key: str) -> tuple[AISearchResponse, int]:
    """Run the guards + orchestrator. Returns (response, tokens_used)."""
    if not question or len(question) > settings.ai_max_question_chars:
        return AISearchResponse(refused=True, reason="off_domain"), 0

    # global budget kill-switch (before spending anything)
    if is_over_budget(db):
        return AISearchResponse(refused=True, reason="budget"), 0

    allowed, _ = check_and_increment_user(db, user_key)
    if not allowed:
        return AISearchResponse(refused=True, reason="limit"), 0

    try:
        result, tokens = answer_question(question)
    except Exception as e:
        logger.error("ai_search failed", error=str(e))
        return AISearchResponse(refused=True, reason="error"), 0

    record_tokens(db, tokens)
    return result, tokens


@router.post("", response_model=AISearchResponse)
@router.post("/", response_model=AISearchResponse)
async def ai_search(
    payload: AISearchRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AISearchResponse:
    started = time.perf_counter()

    question = (payload.question or "").strip()

    # stable per-user identity (cookie + IP), set cookie if absent — computed up front so every
    # event (including refusals) can be attributed to a user.
    uid = request.cookies.get("rankair_uid")
    if not uid:
        uid = secrets.token_hex(16)
        response.set_cookie(
            "rankair_uid", uid, max_age=60 * 60 * 24 * 400, httponly=True, samesite="lax"
        )
    client_ip = _client_ip(request)
    user_key = make_user_key(client_ip, uid)

    result, tokens = _resolve(db, question, user_key)

    # Every refusal leaves here with the words the user will actually read. This is the single seam
    # all of them pass through (length check, budget, per-user limit, off-domain, empty result,
    # internal error), so no path can return a null answer and no path needs its own wording.
    # Doing it here rather than in answer_question keeps the service layer's contract untouched:
    # there, an empty result is still a typed refusal with answer=None (see test_ai_search_no_data).
    # Two outcomes only, never a third: a real answer from the data, or this one. A blank string
    # counts as no answer (the LLM occasionally returns one), so it is replaced too.
    if not (result.answer or "").strip():
        result.answer = refusal_answer(result.reason, question)

    # analytics: one row per request, best-effort (never breaks the user's response). Runs in a
    # threadpool so the blocking country lookup + DB write don't stall the event loop.
    latency_ms = int((time.perf_counter() - started) * 1000)
    try:
        await run_in_threadpool(
            record_event,
            db,
            question=question,
            answer=result.answer,
            user_key=user_key,
            ip=client_ip,
            refused=result.refused,
            reason=result.reason,
            tokens=tokens,
            latency_ms=latency_ms,
            handler=result.source,
            row_count=len(result.rows),
        )
    except Exception as e:
        logger.warning("record_event failed", error=str(e))

    return result
