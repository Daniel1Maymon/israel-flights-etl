"""
flight_status.py — the single canonical definition of "is this flight cancelled?".

The upstream feed stores cancellations as status_en='CANCELED' (American, one L) and
status_he='מבוטלת' (contains 'בוטל'). Detecting cancellation ad-hoc at each call-site let the
definitions drift: one site searched status_en for British '%cancelled%' (two L's), which matches
ZERO rows — cancellations there were only ever caught by the Hebrew branch, one upstream wording
change away from silently counting every cancelled flight as on-time again.

Define it once, here, and use it everywhere:
  - '%cancel%' matches CANCELED / CANCELLED / canceled / cancelled, so an English spelling/casing
    change upstream cannot silently zero out the count.
  - status_he '%בוטל%' is kept as a redundant safety net (matches 'בוטל' / 'מבוטלת').

Two forms are exported: a raw-SQL fragment for text() queries and a SQLAlchemy predicate for the ORM.
Keep them equivalent — that equivalence is the whole point of centralising here.
"""
from __future__ import annotations

# Raw-SQL fragment for text() queries. Assumes the `flights` table (bare, unaliased column names).
CANCELLED_SQL = "(status_en ILIKE '%cancel%' OR status_he ILIKE '%בוטל%')"
NOT_CANCELLED_SQL = f"NOT {CANCELLED_SQL}"


def is_cancelled(model):
    """SQLAlchemy predicate: True when the flight row is cancelled. Mirror of CANCELLED_SQL."""
    from sqlalchemy import or_

    return or_(model.status_en.ilike("%cancel%"), model.status_he.ilike("%בוטל%"))
