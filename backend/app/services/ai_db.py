"""
ai_db.py — the read-only database engine for AI search.

All AI-search queries (query handlers AND the generated-SQL fallback) run through this engine, which
connects as the least-privilege `rankair_ro` role (SELECT on `flights` only, 2s statement_timeout).
This is the hard security backstop: even a fully-compromised LLM cannot write, drop, or read
anything but `flights` here.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

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
