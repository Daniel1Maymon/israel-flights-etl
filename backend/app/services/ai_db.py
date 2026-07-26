"""
ai_db.py — the read-only database engine for AI search.

All AI-search queries (query handlers AND the generated-SQL fallback) run through this engine, which
connects as the least-privilege `rankair_ro` role (SELECT on `flights` only, 2s statement_timeout).
This is the hard security backstop: even a fully-compromised LLM cannot write, drop, or read
anything but `flights` here.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any, Optional

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

logger = structlog.get_logger()

_ro_engine: Optional[Engine] = None


def get_ro_engine() -> Engine:
    """Lazily build the read-only engine from DATABASE_URL_RO."""
    global _ro_engine
    if _ro_engine is None:
        url = settings.database_url_ro
        if not url:
            raise RuntimeError("DATABASE_URL_RO is not configured (read-only role for AI search).")
        # normalize to the psycopg driver used elsewhere
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _ro_engine = create_engine(
            url, pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800
        )
    return _ro_engine


def run_readonly(sql: str, params: Optional[dict[str, Any]] = None) -> tuple[list[str], list[dict]]:
    """Execute a read-only SELECT and return (columns, rows). Rows are plain dicts."""
    engine = get_ro_engine()
    with engine.connect() as conn:
        # belt-and-suspenders: force the transaction read-only even though the role already is
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = [dict(r._mapping) for r in result]
    return columns, rows


# The window moves by minutes per ETL run, so an hour-stale value is still accurate to the day
# and keeps this query off the per-request path.
_WINDOW_TTL_SECONDS = 3600.0
_window_cache: Optional[tuple[float, tuple[date, date]]] = None


def get_data_window() -> Optional[tuple[date, date]]:
    """
    Earliest and latest scheduled_time in `flights`, as dates — what the data actually covers.

    Two callers need it and both are about honesty: the SQL prompt (an LLM that doesn't know the
    range writes date-blind queries) and the no-rows message (which claims a coverage window to
    the user). A wrong window is worse than no window, so any failure returns None and callers
    drop the claim rather than guess.

    Failures are not cached: they mean the read-only engine is down, in which case the request's
    own query is about to fail through the same engine anyway.
    """
    global _window_cache
    now = time.monotonic()
    if _window_cache and now - _window_cache[0] < _WINDOW_TTL_SECONDS:
        return _window_cache[1]

    try:
        _, rows = run_readonly("SELECT MIN(scheduled_time) AS lo, MAX(scheduled_time) AS hi FROM flights")
    except Exception as e:
        logger.warning("could not read data window", error=str(e))
        return None

    lo, hi = (rows[0]["lo"], rows[0]["hi"]) if rows else (None, None)
    if not lo or not hi:
        return None

    window = (lo.date(), hi.date())
    _window_cache = (now, window)
    return window
