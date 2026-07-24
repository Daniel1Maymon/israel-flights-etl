"""
analytics.py — per-request event log for AI search + read-only aggregates for the admin dashboard.

Complements ratelimit.py: where ai_usage/ai_budget hold only counters, ai_events holds ONE row per
question (the text people typed, whether it was answered or refused, tokens, latency). Writes go
through the normal writable Session; the read aggregates power GET /api/v1/admin/*.

Privacy note: user_key is the same SHA-256(IP+cookie) hash used for rate limiting — raw IPs are
never stored. Question text IS stored verbatim (that is the point of the feature).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# Blended $/1M tokens estimate for gemini-2.5-flash (input+output), matches the ~$6-8 / 20M
# figure in config.py. Adjust if the provider/model changes.
COST_PER_1M_TOKENS = 0.35

# Idempotent DDL so a fresh deploy self-heals (mirrors ratelimit.py's pattern).
_DDL = """
CREATE TABLE IF NOT EXISTS ai_events (
    id          BIGSERIAL   PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_key    TEXT,
    question    TEXT        NOT NULL,
    refused     BOOLEAN     NOT NULL DEFAULT FALSE,
    reason      TEXT,
    tokens      INT         NOT NULL DEFAULT 0,
    latency_ms  INT,
    handler     TEXT,
    row_count   INT
);
CREATE INDEX IF NOT EXISTS ix_ai_events_created_at ON ai_events (created_at DESC);
"""


def ensure_events_table(engine: Engine) -> None:
    """Create the events table + index if missing (call at startup and before reads)."""
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in _DDL.split(";"))):
            conn.exec_driver_sql(stmt)


def record_event(
    db: Session,
    *,
    question: str,
    user_key: str | None,
    refused: bool,
    reason: str | None,
    tokens: int,
    latency_ms: int,
    handler: str | None,
    row_count: int | None,
) -> None:
    """Insert one event row. Callers wrap this so analytics can never break the user request."""
    db.execute(
        text("""
            INSERT INTO ai_events
                (user_key, question, refused, reason, tokens, latency_ms, handler, row_count)
            VALUES
                (:user_key, :question, :refused, :reason, :tokens, :latency_ms, :handler, :row_count)
        """),
        {
            "user_key": user_key,
            "question": question,
            "refused": refused,
            "reason": reason,
            "tokens": int(tokens or 0),
            "latency_ms": int(latency_ms),
            "handler": handler,
            "row_count": row_count,
        },
    )
    db.commit()


def get_metrics(db: Session) -> dict[str, Any]:
    """Aggregate KPIs + timeseries for the dashboard. Safe on an empty table (returns zeros)."""
    totals = db.execute(
        text("""
            SELECT
                COUNT(*)                                                AS total_questions,
                COUNT(DISTINCT user_key)                                AS unique_users,
                COALESCE(SUM(tokens), 0)                                AS total_tokens,
                COALESCE(AVG(CASE WHEN refused THEN 1.0 ELSE 0.0 END), 0) AS refusal_rate,
                COALESCE(percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms), 0) AS p50,
                COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) AS p95
            FROM ai_events
        """)
    ).mappings().one()

    per_day = db.execute(
        text("""
            SELECT to_char(created_at::date, 'YYYY-MM-DD') AS day, COUNT(*) AS count
            FROM ai_events
            WHERE created_at >= CURRENT_DATE - INTERVAL '29 days'
            GROUP BY 1
            ORDER BY 1
        """)
    ).mappings().all()

    by_reason = db.execute(
        text("""
            SELECT COALESCE(reason, 'unknown') AS reason, COUNT(*) AS count
            FROM ai_events
            WHERE refused
            GROUP BY 1
            ORDER BY 2 DESC
        """)
    ).mappings().all()

    total_tokens = int(totals["total_tokens"])
    return {
        "total_questions": int(totals["total_questions"]),
        "unique_users": int(totals["unique_users"]),
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(total_tokens / 1_000_000 * COST_PER_1M_TOKENS, 4),
        "refusal_rate": round(float(totals["refusal_rate"]), 4),
        "p50_latency_ms": int(totals["p50"]),
        "p95_latency_ms": int(totals["p95"]),
        "questions_per_day": [dict(r) for r in per_day],
        "refusals_by_reason": [dict(r) for r in by_reason],
    }


def get_recent_events(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    """The 'what people wrote' feed — newest first."""
    rows = db.execute(
        text("""
            SELECT
                to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                question, refused, reason, tokens, latency_ms, handler, row_count
            FROM ai_events
            ORDER BY created_at DESC
            LIMIT :n
        """),
        {"n": limit},
    ).mappings().all()
    return [dict(r) for r in rows]
