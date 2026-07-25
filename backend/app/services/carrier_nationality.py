"""
carrier_nationality.py — the single canonical definition of "is this an Israeli carrier?".

Sibling of `flight_status.py`, and it exists for exactly the same reason. The Israeli/foreign split
is the backbone of the crisis analysis (during March-April 2026 foreign carriers cancelled ~81% of
their departures while Israeli carriers cancelled ~40% and then GREW their schedule), so a
call-site that quietly disagrees about which carriers count as Israeli silently changes the
headline number on a public page.

The trap this module exists to prevent: the obvious four (El Al, Arkia, Israir, Sun d'Or) are easy
to remember, and Air Haifa (E2) is easy to forget. Air Haifa flew 231 departures in March 2026 with
a 20.8% cancellation rate — filed under "foreign" it drags the foreign cancellation rate DOWN by
several points and understates the very gap the page is about.

Do NOT infer nationality from `country_en` on a flight row: for a departure that column holds the
DESTINATION country, so `country_en = 'Israel'` matches domestic/Eilat/Haifa legs of foreign
carriers, not Israeli airlines.

Two forms are exported: a raw-SQL fragment for text() queries and a SQLAlchemy predicate for the
ORM. Keep them equivalent — that equivalence is the whole point of centralising here.
"""
from __future__ import annotations

# Israeli passenger carriers operating scheduled service from TLV.
#   LY = El Al, IZ = Arkia, 6H = Israir, ER = Sun d'Or (El Al leisure arm), E2 = Air Haifa
# Cargo (ICL / C.A.L.) and state operators (IAF) are deliberately excluded: the public pages all
# describe passenger service, and mixing cargo into "flights an Israeli airline operated" would
# overstate the schedule ordinary travellers could actually book.
ISRAELI_CARRIER_CODES: frozenset[str] = frozenset({"LY", "IZ", "6H", "ER", "E2"})

# Rendered as a SQL literal list once, so the fragment and the ORM predicate cannot drift apart
# by someone editing one list and not the other.
_CODES_SQL = ", ".join(f"'{code}'" for code in sorted(ISRAELI_CARRIER_CODES))

ISRAELI_CARRIER_SQL = f"(airline_code IN ({_CODES_SQL}))"
FOREIGN_CARRIER_SQL = f"(airline_code IS NULL OR airline_code NOT IN ({_CODES_SQL}))"


def is_israeli_carrier(model):
    """SQLAlchemy predicate: True when the row is an Israeli carrier. Mirror of ISRAELI_CARRIER_SQL."""
    return model.airline_code.in_(sorted(ISRAELI_CARRIER_CODES))


def nationality_of(airline_code: str | None) -> str:
    """
    Classify a single airline code as 'israeli' or 'foreign'.

    Used by the pure aggregation helpers in `insights_logic.py`, which work on plain rows so they
    stay testable without a PostgreSQL-specific query behind them.
    """
    if not airline_code:
        return "foreign"
    return "israeli" if airline_code.strip().upper() in ISRAELI_CARRIER_CODES else "foreign"
