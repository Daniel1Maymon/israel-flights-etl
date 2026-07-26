"""
Admin endpoints — GET /api/v1/admin/metrics, /events, /whoami, and the LLM kill switch at /llm.

Token-gated (ADMIN_TOKEN). These expose real users' questions, so they must never be public:
if ADMIN_TOKEN is unset, every request is rejected. Everything here was read-only until the kill
switch; POST /llm is the one write, and the same gate covers it because the dependency is declared
on the router rather than per-endpoint.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.ai_flags import get_llm_flag, set_llm_enabled
from app.services.analytics import get_metrics, get_recent_events


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Fail closed: no token configured -> deny; otherwise require `Authorization: Bearer <token>`."""
    expected = settings.admin_token
    if not expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    # compare_digest, not `!=`: a plain string comparison returns as soon as two bytes differ, so
    # how long the reject takes leaks how much of the token was right, and the secret can be
    # recovered a character at a time. The detail is never more than "unauthorized" for the same
    # reason -- an error that says what was expected hands over the thing it is protecting.
    if not secrets.compare_digest(authorization or "", f"Bearer {expected}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict:
    # DDL removed from the request path: it ALTERs ai_events (AccessExclusiveLock), and
    # two workers serving the dashboard concurrently deadlocked. Tables are created at
    # startup instead -- see app.main lifespan.
    return get_metrics(db)


@router.get("/events")
def events(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    return {"events": get_recent_events(db, limit)}


class LLMFlagUpdate(BaseModel):
    """
    The state to set, never a flip.

    A `/toggle` that read-then-inverted would race: two dashboards open, or one double-click, and
    the two requests read the same value and both write its opposite, landing on whichever lost.
    Sending the wanted state makes the button idempotent — pressing "off" twice leaves it off.
    """
    enabled: bool
    note: str | None = Field(default=None, max_length=200, description="Why, for the audit trail")


@router.get("/llm")
def llm_flag(db: Session = Depends(get_db)) -> dict:
    """Current state of the AI kill switch — what the dashboard button colours itself from."""
    return get_llm_flag(db)


@router.post("/llm")
def set_llm_flag(payload: LLMFlagUpdate, db: Session = Depends(get_db)) -> dict:
    """
    Turn AI search on or off for everyone, immediately.

    Off means the /ai-search endpoint refuses before it reaches an LLM provider: no tokens are
    spent, and the visitor is told the feature is off rather than that we have no data. The rest of
    the site — flight board, rankings, destination search — is untouched.
    """
    return set_llm_enabled(db, payload.enabled, payload.note)


@router.get("/whoami")
def whoami(request: Request) -> dict:
    """
    The forwarding chain as this deploy actually receives it, and who we conclude the caller is.

    TRUSTED_PROXY_HOPS cannot be reasoned out from the platform's docs — it depends on how many
    proxies sit in front on the day. Guessing it wrong is not a small error: too high lets a caller
    forge their identity, too low charges every visitor to the edge's address, which is how real
    users ended up refused at question eleven. Open this from the browser you want counted and read
    the answer off the chain.

    Admin-gated with everything else here: the headers can carry another visitor's address.
    """
    from app.api.ai_search import _client_ip  # local: avoids a cycle with the search router

    chain = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    return {
        "resolved_ip": _client_ip(request),
        "trusted_proxy_hops": settings.trusted_proxy_hops,
        "x_forwarded_for": chain,
        "x_forwarded_for_raw": request.headers.get("x-forwarded-for"),
        "real_ip_headers": {
            h: request.headers.get(h)
            for h in ("cf-connecting-ip", "true-client-ip", "x-real-ip", "x-envoy-external-address")
            if request.headers.get(h)
        },
        "socket_peer": request.client.host if request.client else None,
        "hint": (
            "resolved_ip should be YOUR address. If it is the platform's edge, raise "
            "TRUSTED_PROXY_HOPS by one for each extra entry to its left in x_forwarded_for."
        ),
    }
