"""
AI Search endpoint — POST /api/v1/ai-search.

Free-text question in → grounded answer + supporting rows out. Applies the cost/abuse guards
(global budget kill-switch, per-user daily cap) before spending any LLM tokens, then delegates
to the stateless orchestrator. All failures return a generic refusal (no internals leaked).
"""
from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
from app.schemas.ai_search import AISearchRequest, AISearchResponse
from app.services.ai_search import answer_question
from app.services.ratelimit import (
    check_and_increment_user,
    ensure_tables,
    is_over_budget,
    make_user_key,
    record_tokens,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/ai-search", tags=["ai-search"])

_tables_ready = False


def _ensure_ready() -> None:
    global _tables_ready
    if not _tables_ready:
        try:
            ensure_tables(engine)
        except Exception as e:  # non-fatal; tables usually already exist
            logger.warning("ensure_tables failed", error=str(e))
        _tables_ready = True


@router.post("", response_model=AISearchResponse)
@router.post("/", response_model=AISearchResponse)
async def ai_search(
    payload: AISearchRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AISearchResponse:
    _ensure_ready()

    question = (payload.question or "").strip()
    if not question or len(question) > settings.ai_max_question_chars:
        return AISearchResponse(refused=True, reason="off_domain")

    # global budget kill-switch (before spending anything)
    if is_over_budget(db):
        return AISearchResponse(refused=True, reason="budget")

    # stable per-user identity (cookie + IP), set cookie if absent
    uid = request.cookies.get("rankair_uid")
    if not uid:
        uid = secrets.token_hex(16)
        response.set_cookie(
            "rankair_uid", uid, max_age=60 * 60 * 24 * 400, httponly=True, samesite="lax"
        )
    client_ip = request.client.host if request.client else None
    user_key = make_user_key(client_ip, uid)

    allowed, _ = check_and_increment_user(db, user_key)
    if not allowed:
        return AISearchResponse(refused=True, reason="limit")

    try:
        result, tokens = answer_question(question)
    except Exception as e:
        logger.error("ai_search failed", error=str(e))
        return AISearchResponse(refused=True, reason="error")

    record_tokens(db, tokens)
    return result
