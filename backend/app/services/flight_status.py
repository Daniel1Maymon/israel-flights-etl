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

# A delay beyond this is not a delay — it is a cancellation the feed happened to record as
# DEPARTED or LANDED.
#
# Nobody waits 48 hours at the gate. A flight that leaves two days after its scheduled time was
# cancelled and its passengers rebooked; the upstream feed simply never changed the status. Left
# untreated these rows corrupt every delay statistic they touch: Arkia's "worst delay" read 2,883
# minutes — ten times that carrier's own 99th percentile — off a single Larnaca service held two
# days during the March-April disruption.
#
# Set at a full day rather than the 25 hours originally specified, because 25 hours left El Al's
# worst delay at 1,499 minutes — 24.98 hours, one minute under the line — which reads exactly like
# the problem it was meant to remove. "More than a full calendar day late" is also the cleaner
# concept: by then the next day's equivalent service has already departed.
#
# The rows above the line are unambiguous: 48h, 41.5h, three IDENTICAL 36.4h Athens arrivals across
# three different carriers (a feed artifact, not three real delays), 30.4h, 25.4h, 25.0h, 24.2h.
# Genuine long delays cluster well below. 16 rows in 151,527 (0.01%) are affected, and the highest
# surviving departure delay becomes 20.1h — so this corrects the statistics without materially
# moving any aggregate.
#
# Raise it back to 1500 for the literal 25-hour rule; it is a one-line change and nothing else
# depends on the value.
MAX_PLAUSIBLE_DELAY_MIN = 1440  # 24 hours

# Raw-SQL fragment for text() queries. Assumes the `flights` table (bare, unaliased column names).
#
# COALESCE is load-bearing: delay_minutes is NULL for flights with no recorded actual time. Without
# it the comparison yields NULL, `status OR NULL` is NULL for a non-cancelled row, and `NOT NULL`
# is NULL too — which would silently drop those rows from BOTH the cancelled and the not-cancelled
# sets, losing them from every aggregate on the site.
CANCELLED_SQL = (
    "(status_en ILIKE '%cancel%' OR status_he ILIKE '%בוטל%'"
    f" OR COALESCE(delay_minutes, 0) > {MAX_PLAUSIBLE_DELAY_MIN})"
)
NOT_CANCELLED_SQL = f"NOT {CANCELLED_SQL}"


def is_cancelled(model):
    """SQLAlchemy predicate: True when the flight row is cancelled. Mirror of CANCELLED_SQL."""
    from sqlalchemy import func, or_

    return or_(
        model.status_en.ilike("%cancel%"),
        model.status_he.ilike("%בוטל%"),
        func.coalesce(model.delay_minutes, 0) > MAX_PLAUSIBLE_DELAY_MIN,
    )
