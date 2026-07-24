"""
analytics.py — per-request event log for AI search + read-only aggregates for the admin dashboard.

Complements ratelimit.py: where ai_usage/ai_budget hold only counters, ai_events holds ONE row per
question (the text people typed, the answer they saw, whether it was answered or refused, tokens,
latency, and country). Writes go through the normal writable Session; the read aggregates power
GET /api/v1/admin/*.

Privacy: user_key is the same SHA-256(IP+cookie) hash used for rate limiting. The raw IP is used
ONLY transiently to resolve a country and is never stored — we keep the country label, not the IP.
Question text and the answer ARE stored verbatim (that is the point of the feature).
"""
from __future__ import annotations

import ipaddress
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# Blended $/1M tokens estimate for gemini-2.5-flash. Official rates (ai.google.dev/gemini-api/docs/pricing,
# paid tier): input $0.30/1M, output $2.50/1M. This app is input-heavy (~3 prompt-heavy calls per
# question, short outputs), so assume ~75% input / 25% output: 0.75*0.30 + 0.25*2.50 = $0.85/1M.
# This is an estimate — total tokens aren't split into input/output. At the 20M/mo ceiling ≈ $17.
COST_PER_1M_TOKENS = 0.85

# Idempotent DDL so a fresh deploy self-heals; the ALTERs migrate an already-existing table.
_DDL = """
CREATE TABLE IF NOT EXISTS ai_events (
    id           BIGSERIAL   PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_key     TEXT,
    question     TEXT        NOT NULL,
    answer       TEXT,
    refused      BOOLEAN     NOT NULL DEFAULT FALSE,
    reason       TEXT,
    tokens       INT         NOT NULL DEFAULT 0,
    latency_ms   INT,
    handler      TEXT,
    row_count    INT,
    country      TEXT,
    country_code TEXT
);
CREATE INDEX IF NOT EXISTS ix_ai_events_created_at ON ai_events (created_at DESC);
ALTER TABLE ai_events ADD COLUMN IF NOT EXISTS answer       TEXT;
ALTER TABLE ai_events ADD COLUMN IF NOT EXISTS country      TEXT;
ALTER TABLE ai_events ADD COLUMN IF NOT EXISTS country_code TEXT;
"""

# Small in-process IP->country cache so repeat visitors cost nothing. Bounded loosely; for a
# low-traffic site this never grows large. Values may be (None, None) for private/unresolvable IPs.
_country_cache: dict[str, tuple[str | None, str | None]] = {}


def ensure_events_table(engine: Engine) -> None:
    """Create/migrate the events table + index if missing (call at startup and before reads)."""
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in _DDL.split(";"))):
            conn.exec_driver_sql(stmt)


def lookup_country(ip: str | None) -> tuple[str | None, str | None]:
    """Best-effort (country, country_code) from an IP. Cached; never raises. The IP is not stored."""
    if not ip:
        return None, None
    if ip in _country_cache:
        return _country_cache[ip]

    result: tuple[str | None, str | None] = (None, None)
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved:
            _country_cache[ip] = result
            return result
        r = httpx.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,countryCode"},
            timeout=1.5,
        )
        data = r.json()
        if data.get("status") == "success":
            result = (data.get("country"), data.get("countryCode"))
    except Exception:
        result = (None, None)

    if len(_country_cache) < 10_000:
        _country_cache[ip] = result
    return result


def record_event(
    db: Session,
    *,
    question: str,
    answer: str | None,
    user_key: str | None,
    ip: str | None,
    refused: bool,
    reason: str | None,
    tokens: int,
    latency_ms: int,
    handler: str | None,
    row_count: int | None,
) -> None:
    """Insert one event row. Callers wrap this so analytics can never break the user request."""
    country, country_code = lookup_country(ip)
    db.execute(
        text("""
            INSERT INTO ai_events
                (user_key, question, answer, refused, reason, tokens, latency_ms,
                 handler, row_count, country, country_code)
            VALUES
                (:user_key, :question, :answer, :refused, :reason, :tokens, :latency_ms,
                 :handler, :row_count, :country, :country_code)
        """),
        {
            "user_key": user_key,
            "question": question,
            "answer": answer,
            "refused": refused,
            "reason": reason,
            "tokens": int(tokens or 0),
            "latency_ms": int(latency_ms),
            "handler": handler,
            "row_count": row_count,
            "country": country,
            "country_code": country_code,
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

    top_countries = db.execute(
        text("""
            SELECT country, country_code, COUNT(*) AS count
            FROM ai_events
            WHERE country IS NOT NULL
            GROUP BY country, country_code
            ORDER BY 3 DESC
            LIMIT 10
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
        "top_countries": [dict(r) for r in top_countries],
    }


def get_recent_events(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    """The 'what people wrote (and saw)' feed — newest first."""
    rows = db.execute(
        text("""
            SELECT
                to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
                question, answer, refused, reason, tokens, latency_ms,
                handler, row_count, country, country_code
            FROM ai_events
            ORDER BY created_at DESC
            LIMIT :n
        """),
        {"n": limit},
    ).mappings().all()
    return [dict(r) for r in rows]
