"""
ai_flags.py — the manual kill switch: one row that says whether the LLM may be called at all.

Sits beside ratelimit.py's two automatic guards (per-user daily cap, global monthly budget). Those
fire on their own when a threshold is crossed; this one is a human decision — an admin watching the
token graph decides the feature costs more than it is worth today and turns it off from the
dashboard. Cheap to flip, cheap to flip back, no deploy.

Where the state lives: Postgres. An environment variable would need a redeploy, which is not a
button. A process variable would not survive a restart and would not reach the other gunicorn
worker — the same reasoning that put the budget counter in a table (DECISIONS #7).

Default when the row is missing: ON. This is the one place the codebase deliberately fails OPEN
(admin_token does the opposite, and should). The exposure here is only cost, and cost is already
bounded above by the monthly budget and the per-user cap; the cost of failing closed is a working
feature going dark on a deploy with nothing in the UI to explain why.

Enforcement is a single check at the endpoint (api/ai_search.py). That covers the whole feature
because every provider call in the codebase runs underneath answer_question() — the four LLM steps
(interpret, resolve_destination, generate_sql, format_answer) are all reached from there, including
the one in destination_resolver.py. It stops covering the whole feature the moment something calls
an LLM from anywhere else: a cron job, a second endpoint. Such a caller must run its own
is_llm_enabled check, or the check moves down into LLMTasks.__init__ where nothing can miss it.
test_ai_kill_switch.py::test_no_llm_call_site_appears_outside_the_guarded_path fails when that day
comes.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.services.schema_init import run_ddl

logger = structlog.get_logger()

# CURRENT_TIMESTAMP rather than now(): identical in Postgres, and it is also what SQLite
# understands, so the tests exercise this exact DDL rather than a hand-written variant.
# The seed row means a fresh deploy starts usable without relying on the missing-row default.
_DDL = """
CREATE TABLE IF NOT EXISTS ai_flags (
    key        TEXT PRIMARY KEY,
    enabled    BOOLEAN     NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note       TEXT
);
INSERT INTO ai_flags (key, enabled) VALUES ('llm', TRUE) ON CONFLICT (key) DO NOTHING;
"""

_LLM_KEY = "llm"


def ensure_flags_table(engine: Engine) -> None:
    """Create + seed the flag table. CALL AT STARTUP ONLY (see schema_init)."""
    run_ddl(engine, _DDL, label="ai_flags")


def is_llm_enabled(db: Session) -> bool:
    """
    True if the LLM may be called. One primary-key read, on every AI-search request.

    Unreadable table -> on, for the same reason a missing row means on, and because this check now
    sits FIRST in the guard ladder: startup DDL is best-effort (app.main logs and continues if the
    database was briefly unreachable), so a table that failed to create would otherwise turn every
    question into a 500 rather than an answer. A switch that can take the feature down by breaking
    is worse than no switch.

    The rollback matters as much as the default: on Postgres a failed statement aborts the
    transaction, and without it every later query on this session — the budget check, the daily
    counter, the analytics write — would fail too.
    """
    try:
        row = db.execute(
            text("SELECT enabled FROM ai_flags WHERE key = :k"), {"k": _LLM_KEY}
        ).scalar()
    except Exception as exc:
        logger.warning("llm switch unreadable, defaulting to on", error=str(exc))
        try:
            db.rollback()
        except Exception:  # pragma: no cover - a session too broken to roll back
            pass
        return True
    return True if row is None else bool(row)  # missing row -> on (see module docstring)


def get_llm_flag(db: Session) -> dict[str, Any]:
    """The full state for the admin dashboard: what it is, when it changed, and why."""
    row = db.execute(
        text("SELECT enabled, updated_at, note FROM ai_flags WHERE key = :k"), {"k": _LLM_KEY}
    ).first()
    if row is None:
        return {"enabled": True, "updated_at": None, "note": None}
    updated_at = row[1]
    return {
        "enabled": bool(row[0]),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        "note": row[2],
    }


def set_llm_enabled(db: Session, enabled: bool, note: str | None = None) -> dict[str, Any]:
    """
    Write the flag and return the new state.

    Takes the state to set, never a flip: two admins on the dashboard at once — or one double-click
    — would otherwise race on a read-then-invert and land on whichever value lost.
    """
    db.execute(
        text("""
            INSERT INTO ai_flags (key, enabled, note) VALUES (:k, :e, :n)
            ON CONFLICT (key) DO UPDATE
              SET enabled = :e, note = :n, updated_at = CURRENT_TIMESTAMP
        """),
        {"k": _LLM_KEY, "e": enabled, "n": note},
    )
    db.commit()
    logger.info("llm switch set", enabled=enabled, note=note)
    return get_llm_flag(db)
