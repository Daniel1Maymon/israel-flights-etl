"""
test_runs.py — what the probe harness costs, kept apart from what users cost.

`scripts/ai_probe.py` calls `answer_question` directly rather than going through the endpoint, so
none of the endpoint's bookkeeping runs: `record_tokens` never fires and `ai_budget` never moves.
The tokens are spent at the provider all the same. Three runs on 2026-07-25 cost 181,111 tokens
that no table in this database knew about.

Why its own table instead of a `channel` column on ai_events: get_metrics() runs six aggregates
over ai_events (unique users, refusal rate, latency percentiles, per-day counts, refusals by
reason, top countries). A channel column makes every one of them wrong until it is filtered, and
wrong again the first time someone adds a seventh and forgets. Synthetic traffic would also skew
the repeat-rate analysis the cache design depends on. A separate table leaves all six queries
untouched -- the failure mode is a missing number, not a silently corrupted one.

One row per RUN, not per question: the jsonl in scripts/ai_probe_results/ already holds the
per-question detail, so this only needs the rollup and a pointer back to it.

Deliberately NOT wired into is_over_budget(). Test spend is real money but it must not be able to
darken the live feature -- a large probe run should never trip the kill switch on rank-air.com.
The dashboard shows both numbers so the true bill stays visible; only the automatic switch is
decoupled.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.services.schema_init import run_ddl

_DDL = """
CREATE TABLE IF NOT EXISTS ai_test_runs (
    id         BIGSERIAL   PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tag        TEXT,
    questions  INT         NOT NULL DEFAULT 0,
    repeats    INT         NOT NULL DEFAULT 1,
    tokens     BIGINT      NOT NULL DEFAULT 0,
    artifact   TEXT
);
CREATE INDEX IF NOT EXISTS ix_ai_test_runs_created_at ON ai_test_runs (created_at DESC);
"""


def ensure_test_runs_table(engine: Engine) -> None:
    """Create the table + index if missing. CALL AT STARTUP ONLY (see schema_init.run_ddl)."""
    run_ddl(engine, _DDL, label="ai_test_runs")


def record_test_run(
    db: Session,
    *,
    tag: str | None,
    questions: int,
    repeats: int,
    tokens: int,
    artifact: str | None,
) -> None:
    """Insert one row for a completed probe run. Callers wrap this -- bookkeeping never fails a run."""
    db.execute(
        text("""
            INSERT INTO ai_test_runs (tag, questions, repeats, tokens, artifact)
            VALUES (:tag, :questions, :repeats, :tokens, :artifact)
        """),
        {
            "tag": tag or None,
            "questions": int(questions),
            "repeats": int(repeats),
            "tokens": int(tokens or 0),
            "artifact": artifact,
        },
    )
    db.commit()


def record_run_safely(
    *, tag: str | None, questions: int, repeats: int, tokens: int, artifact: str | None
) -> bool:
    """
    Record a run from a standalone harness. Never raises; returns whether the row was written.

    Shared so the next harness is one line rather than another copy of the session handling --
    ai_probe.py was only the first producer, and every one that calls answer_question() directly
    has the same invisible spend.

    Two ways it declines, both deliberate:
      - RANKAIR_RECORD_TEST_RUNS=0 turns it off. A suite run dozens of times a day should not
        write to production on every invocation; set this while iterating locally.
      - No writable DATABASE_URL. answer_question() reaches the database through the READ-ONLY
        role, so a harness may have no write path at all. Bookkeeping must never fail a run --
        the caller prints its total either way, and backfill_test_runs.py can import it later.
    """
    import os

    if os.getenv("RANKAIR_RECORD_TEST_RUNS", "1") == "0":
        return False
    try:
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            ensure_test_runs_table(db.get_bind())
            record_test_run(
                db,
                tag=tag,
                questions=questions,
                repeats=repeats,
                tokens=tokens,
                artifact=artifact,
            )
            return True
        finally:
            db.close()
    except Exception:
        return False


def get_test_metrics(db: Session) -> dict[str, Any]:
    """
    This month's probe spend, plus the recent runs.

    Scoped to the calendar month so it lines up with ai_budget's period, which is what the
    combined figure on the dashboard is compared against. Safe on an empty table (returns zeros).
    """
    totals = db.execute(
        text("""
            SELECT
                COALESCE(SUM(tokens), 0) AS tokens,
                COUNT(*)                 AS runs
            FROM ai_test_runs
            WHERE to_char(created_at, 'YYYY-MM') = to_char(CURRENT_DATE, 'YYYY-MM')
        """)
    ).mappings().one()

    recent = db.execute(
        text("""
            SELECT
                to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                tag, questions, repeats, tokens, artifact
            FROM ai_test_runs
            ORDER BY created_at DESC
            LIMIT 20
        """)
    ).mappings().all()

    return {
        "test_tokens_this_month": int(totals["tokens"]),
        "test_runs_this_month": int(totals["runs"]),
        "recent_test_runs": [dict(r) for r in recent],
    }
