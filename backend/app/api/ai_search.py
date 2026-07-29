"""
AI Search endpoint — POST /api/v1/ai-search.

Free-text question in → grounded answer + supporting rows out. Applies the cost/abuse guards
(global budget kill-switch, per-user daily cap) before spending any LLM tokens, then delegates
to the stateless orchestrator. Failures refuse without leaking internals, but not identically:
a cost outage and a fault are told apart here, because they are told apart to the user
(see services/refusal_text.py).

Every request also writes one analytics event (see services/analytics.py) — best-effort, never
allowed to break the user path.
"""
from __future__ import annotations

import ipaddress
import secrets
import time

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
from app.schemas.ai_search import AISearchRequest, AISearchResponse
from app.services.ai_flags import is_llm_enabled
from app.services.ai_search import answer_question
from app.services.analytics import record_event
from app.services.llm import LLMQuotaExceeded
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


# Headers a CDN or edge sets to the address it saw the browser connect from. Where one exists it
# beats parsing X-Forwarded-For, because the edge knows the answer and we would be guessing at it.
_REAL_IP_HEADERS = ("cf-connecting-ip", "true-client-ip", "x-real-ip")


def _usable(candidate: str) -> str | None:
    """A routable address, or None for garbage, private hops and loopback."""
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
        return None
    return candidate


def _client_ip(request: Request) -> str | None:
    """
    The visitor's address — counted against the daily cap, so both halves matter.

    Read the LEFT end and a caller can mint a new identity per request by sending their own
    X-Forwarded-For. Read the right end and you get the last proxy that touched the request, which
    every visitor shares: this shipped, and Railway's edge (152.233.x.x) became a single bucket that
    all traffic drained, refusing real users at question eleven.

    Neither end is the answer. Each proxy appends the peer it saw, so the browser's address sits a
    FIXED number of hops from the right — one per proxy in front of the app. TRUSTED_PROXY_HOPS says
    how many, anything further left is caller-supplied and ignored. GET /api/v1/admin/whoami prints
    the live chain to set it from, rather than from a guess about the platform's topology.
    """
    for header in _REAL_IP_HEADERS:
        value = (request.headers.get(header) or "").strip()
        if value and _usable(value):
            return value

    xff = request.headers.get("x-forwarded-for")
    if xff:
        chain = [p.strip() for p in xff.split(",") if p.strip()]
        # Index of the browser: as many hops from the right as there are proxies in front of us.
        start = max(0, len(chain) - 1 - settings.trusted_proxy_hops)
        for candidate in reversed(chain[: start + 1]):
            if _usable(candidate):
                return candidate
    return request.client.host if request.client else None


def _resolve(db: Session, question: str, user_key: str) -> tuple[AISearchResponse, int]:
    """Run the guards + orchestrator. Returns (response, tokens_used)."""
    # Manual kill switch, first rung on the ladder (see services/ai_flags.py). Two reasons it sits
    # above everything else rather than beside the budget check:
    #   - above the daily cap, so a visitor is not charged one of their ten questions for a feature
    #     that is switched off and answered nobody;
    #   - above the length check, so a blank or over-long question sent while the feature is off is
    #     told THAT, instead of "I don't have data that answers that" — which describes a different
    #     system state and sends the user away for the wrong reason.
    if not is_llm_enabled(db):
        return AISearchResponse(refused=True, reason="llm_off"), 0

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
    except LLMQuotaExceeded as e:
        # A provider ceiling — a spend cap, a quota, a rate limit — is a cost outage, not a fault,
        # and the user is told so (see refusal_text.budget_text). Caught ABOVE the generic handler
        # because it used to fall into it: a Google spend cap became reason='error' and the site
        # answered "I don't have data that answers that" to every question it can answer. The
        # provider's own sentence goes to the log, where it names the cap that has to be raised.
        logger.error("ai_search provider quota exhausted", error=str(e))
        return AISearchResponse(refused=True, reason="provider_quota"), 0
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
    # all of them pass through (kill switch, length check, budget, per-user limit, off-domain,
    # empty result, internal error), so no path can return a null answer or need its own wording.
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
