"""
Admin analytics endpoints — GET /api/v1/admin/metrics and /api/v1/admin/events.

Token-gated (ADMIN_TOKEN). These expose real users' questions, so they must never be public:
if ADMIN_TOKEN is unset, every request is rejected. Read-only aggregates over ai_events.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.analytics import get_metrics, get_recent_events


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Fail closed: no token configured -> deny; otherwise require `Authorization: Bearer <token>`."""
    expected = settings.admin_token
    if not expected or authorization != f"Bearer {expected}":
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
