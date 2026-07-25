"""
Serialised, idempotent DDL execution.

Why this exists: the ai_events DDL ends in `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
which takes an AccessExclusiveLock. The block also runs `CREATE INDEX IF NOT EXISTS`
first, which takes a ShareLock. Two workers running the block concurrently therefore
both hold ShareLock and both try to upgrade to AccessExclusiveLock -- a lock-upgrade
deadlock, observed in production as:

    psycopg.errors.DeadlockDetected: deadlock detected
    Process A waits for AccessExclusiveLock on relation 30223; blocked by process B.
    Process B waits for AccessExclusiveLock on relation 30223; blocked by process A.

A transaction-scoped advisory lock makes concurrent callers queue instead of deadlock.
It is released automatically when the transaction ends, including on error.
"""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = structlog.get_logger()

# Arbitrary but fixed application-wide key. Every DDL runner uses the same one so that
# all schema initialisation across all workers serialises against a single lock.
_SCHEMA_LOCK_KEY = 8_147_320_615


def run_ddl(engine: Engine, ddl: str, *, label: str) -> None:
    """
    Execute a semicolon-separated idempotent DDL block under an advisory lock.

    Call at startup, never on the request path: even serialised, DDL takes exclusive
    locks that stall concurrent readers of the same table.
    """
    statements = [s.strip() for s in ddl.split(";") if s.strip()]
    if not statements:
        return

    with engine.begin() as conn:
        # Advisory locks are Postgres-only; tests run on SQLite, where the whole
        # concurrency problem does not arise.
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SCHEMA_LOCK_KEY})
        for stmt in statements:
            conn.exec_driver_sql(stmt)

    logger.info("schema ensured", block=label, statements=len(statements))
