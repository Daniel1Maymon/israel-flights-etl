"""
ratelimit.py — cost/abuse guards for AI search, backed by two Postgres tables.

- Per-user daily cap  (ai_usage)  — stops one identity from spamming.
- Global monthly budget kill-switch (ai_budget) — survives identity rotation; when the token
  ceiling is hit the feature degrades to the plain destination search.

Counters are WRITES, so they use the normal writable Session — NOT the read-only AI role.
All upserts are atomic (INSERT ... ON CONFLICT DO UPDATE).
"""
from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.services.schema_init import run_ddl

# Idempotent DDL so a fresh deploy recreates the counters (mirrors what we created on the DB).
_DDL = """
CREATE TABLE IF NOT EXISTS ai_usage (
    user_key TEXT NOT NULL,
    day      DATE NOT NULL,
    count    INT  NOT NULL DEFAULT 0,
    PRIMARY KEY (user_key, day)
);
CREATE TABLE IF NOT EXISTS ai_budget (
    period        TEXT   NOT NULL,
    tokens_used   BIGINT NOT NULL DEFAULT 0,
    request_count INT    NOT NULL DEFAULT 0,
    PRIMARY KEY (period)
);
"""


def ensure_tables(engine: Engine) -> None:
    """Create the counter tables if missing. CALL AT STARTUP ONLY (see schema_init)."""
    run_ddl(engine, _DDL, label="ai_counters")


def make_user_key(client_ip: str | None, cookie_id: str | None) -> str:
    """
    Identity for the daily cap: the client IP, hashed.

    Hashed here because a counter needs no more than an identity. The raw address is kept
    separately on the ai_events row, where the admin dashboard shows it — so "the IP is never
    stored" is no longer true of the system, only of this table.

    It used to be IP + cookie, which cancelled the cap out entirely. The cookie is set
    SameSite=Lax and the frontend and API are different sites, so the browser never sends it back
    on the API call — every request arrived cookie-less, got a fresh uid, and hashed to a key that
    had never been seen. The counter therefore read 1 forever.

    IP alone is the weaker signal and the one that actually works: a shared NAT means several
    people draw on one quota, and a phone switching networks gets a fresh one. That is the trade
    for a cap that exists. Adding the cookie back — as a way to SPLIT a shared IP, never to widen
    it — is a later step, and needs SameSite=None; Secure first.
    """
    raw = client_ip or f"cookie:{cookie_id or ''}"  # no IP (tests, odd proxies): fall back
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_and_increment_user(db: Session, user_key: str) -> tuple[bool, int]:
    """Atomically bump today's counter. Returns (allowed, count_after)."""
    count = db.execute(
        text("""
            INSERT INTO ai_usage (user_key, day, count) VALUES (:k, CURRENT_DATE, 1)
            ON CONFLICT (user_key, day) DO UPDATE SET count = ai_usage.count + 1
            RETURNING count
        """),
        {"k": user_key},
    ).scalar_one()
    db.commit()
    return count <= settings.ai_daily_limit_per_user, count


def is_over_budget(db: Session) -> bool:
    """True if this month's token usage has passed the configured ceiling."""
    used = db.execute(
        text("SELECT tokens_used FROM ai_budget WHERE period = to_char(CURRENT_DATE,'YYYY-MM')")
    ).scalar()
    return bool(used is not None and used > settings.ai_monthly_budget_tokens)


def record_tokens(db: Session, tokens: int) -> None:
    """Add token usage to the current month's budget row."""
    if tokens <= 0:
        return
    db.execute(
        text("""
            INSERT INTO ai_budget (period, tokens_used, request_count)
            VALUES (to_char(CURRENT_DATE,'YYYY-MM'), :t, 1)
            ON CONFLICT (period) DO UPDATE
              SET tokens_used = ai_budget.tokens_used + :t,
                  request_count = ai_budget.request_count + 1
        """),
        {"t": int(tokens)},
    )
    db.commit()
