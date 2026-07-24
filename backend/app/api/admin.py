"""
Admin analytics endpoints — GET /api/v1/admin/metrics and /api/v1/admin/events.

Token-gated (ADMIN_TOKEN). These expose real users' questions, so they must never be public:
if ADMIN_TOKEN is unset, every request is rejected. Read-only aggregates over ai_events.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
from app.services.analytics import ensure_events_table, get_metrics, get_recent_events


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
    ensure_events_table(engine)  # self-heal if no event has been recorded yet
    return get_metrics(db)


@router.get("/events")
def events(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    ensure_events_table(engine)
    return {"events": get_recent_events(db, limit)}
