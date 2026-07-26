"""
ai_query_handlers.py — reviewed, parameter-bound query handlers for AI search (the correct+safe path).

Each handler owns the full build → run → return round trip for one shape of question: it builds
the SQL, executes it via ai_db.run_readonly(), and returns (columns, rows). The LLM only supplies
validated parameters (destination, airline, metric, sort, limit) — never SQL. Each handler bakes
in the data quirks (CANCELED via ILIKE, NULL-safe delay, min-10 sample, city match via location_he/en).

Anything not matching a handler raises NoQueryHandlerMatch → the orchestrator uses the
generated-SQL fallback (guarded by sql_guard + the read-only role).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services.ai_db import get_ro_engine, run_readonly
from app.services.carrier_recovery import compute_carrier_recovery
from app.services.flight_status import CANCELLED_SQL, NOT_CANCELLED_SQL

# Common metric projection reused by every handler.
# On-time and avg-delay EXCLUDE cancelled flights: a cancelled flight is not "on time", and its
# delay_minutes is junk (values up to ±2700). Denominator stays total (so cancels lower on-time%).
# Cancellation detection is the canonical one from flight_status (see that module for why).
_METRICS_SELECT = f"""
    COUNT(*) AS total_flights,
    ROUND(100.0 * SUM(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes <= 15 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct,
    ROUND(100.0 * SUM(CASE WHEN {CANCELLED_SQL} THEN 1 ELSE 0 END) / COUNT(*), 1) AS cancel_pct,
    ROUND(AVG(CASE WHEN {NOT_CANCELLED_SQL} AND delay_minutes > 0 THEN delay_minutes END), 1) AS avg_delay_minutes
"""

# metric -> (order column, default direction for "best first")
_METRIC = {
    "on_time": ("on_time_pct", "DESC"),
    "cancel": ("cancel_pct", "ASC"),
    "delay": ("avg_delay_minutes", "ASC"),
}

# Europe region -> country_en values actually present in the data.
_REGIONS: dict[str, list[str]] = {
    "europe": [
        "ALBANIA", "AUSTRIA", "BELARUS", "BELGIUM", "BOSNIA", "BULGARIA", "CROATIA", "CYPRUS",
        "CZECH REPUBLIC", "DENMARK", "FINLAND", "FRANCE", "GEORGIA", "GERMANY", "GREECE",
        "HUNGARY", "ICELAND", "IRELAND", "ITALY", "LATVIA", "LITHUANIA", "MALTA", "MOLDOVA",
        "MONTENEGRO", "NETHERLANDS", "NORWAY", "POLAND", "PORTUGAL", "ROMANIA", "SERBIA",
        "SLOVAKIA", "SLOVENIA", "SPAIN", "SWITZERLAND", "UNITED KINGDOM",
    ],
}


class NoQueryHandlerMatch(Exception):
    """No reviewed query handler fits this intent → use the generated-SQL fallback."""


# For each metric, which SQL direction puts the BEST carrier first. "worst" is the inverse.
# The LLM used to hand us a raw `sort` of asc|desc and it flipped between identical runs, so the
# same question named ISRAIR one time and BLUE BIRD the next. It now says only which END of the
# ranking the user wants; the direction is arithmetic, and arithmetic belongs in code.
_BEST_FIRST = {"on_time": "DESC", "cancel": "ASC", "delay": "ASC"}


def _ordering(intent: dict) -> tuple[str, str]:
    """Return (ORDER BY clause, a phrase describing it) for the requested metric + superlative."""
    metric = intent.get("metric") if intent.get("metric") in _METRIC else "on_time"
    col, _ = _METRIC[metric]
    worst = (intent.get("superlative") or "best").strip().lower() == "worst"
    direction = _BEST_FIRST[metric]
    if worst:
        direction = "ASC" if direction == "DESC" else "DESC"
    phrase = {
        ("on_time", False): "most punctual first", ("on_time", True): "least punctual first",
        ("cancel", False): "fewest cancellations first", ("cancel", True): "most cancellations first",
        ("delay", False): "shortest average delay first", ("delay", True): "longest average delay first",
    }[(metric, worst)]
    return f"ORDER BY {col} {direction} NULLS LAST", phrase


def _limit(intent: dict) -> int:
    try:
        n = int(intent.get("limit") or 10)
    except (TypeError, ValueError):
        n = 10
    return max(1, min(n, settings.ai_max_rows))


def _dest_clause(destination: str, params: dict, kind: str = "city") -> str:
    """
    Filter on a destination the orchestrator has already resolved to a value present in the data.

    Exact equality on one column, not a wildcard across four. The old `ILIKE '%text%'` was doing
    two jobs badly: it tried to be the resolver (and failed on any name the data stores
    differently), and it over-matched short fragments. Resolution now happens once, up front, in
    destination_resolver; by the time a handler runs, `destination` is a canonical
    location_city_en or country_en value.

    Case-insensitive but not wildcarded: the canonical values are stored upper-case, and a caller
    passing "London" means the same place as "LONDON" — while "LON" still means nothing.
    """
    params["dest"] = destination.strip()
    column = "country_en" if kind == "country" else "location_city_en"
    return f"UPPER({column}) = UPPER(:dest)"


def _run(sql: str, params: dict) -> tuple[list[str], list[dict]]:
    return run_readonly(sql, params)


# Rows alone do not say what they ARE. Handed ten carriers sorted by punctuality, the format step
# called the last one "the least punctual" -- true of those ten, false of the 104 that exist -- and
# presented ten rows as "all airlines". It cannot know better from a list of dicts, so every
# ranking now ships a description of itself alongside the data.
_MIN_SAMPLE = 10


def _ranked(sql: str, params: dict, intent: dict, order_phrase: str,
            group_col: str, where_sql: str) -> tuple[list[str], list[dict], dict]:
    """Run a ranking query and report its shape: how many groups exist, how many came back, why."""
    columns, rows = _run(sql, params)
    _, totals = _run(
        f"SELECT COUNT(*) AS n FROM (SELECT {group_col} FROM flights WHERE {where_sql} "
        f"GROUP BY {group_col} HAVING COUNT(*) >= {_MIN_SAMPLE}) t",
        params,
    )
    total = int(totals[0]["n"]) if totals else len(rows)
    return columns, rows, {
        "total_matching": total,
        "returned": len(rows),
        "truncated": total > len(rows),
        "ordered_by": order_phrase,
        "min_sample": _MIN_SAMPLE,
    }


# What each countable thing aggregates, mirroring app/api/stats.py exactly. These are the numbers
# in the dashboard's headline bar, and AI search contradicting the bar on the same page is a bug
# regardless of which one you prefer -- so the aggregate, the departures scoping and the absence
# of a time filter are all copied from there rather than reasoned out again here.
_COUNTABLE = {
    "flights": ("COUNT(*)", "total_flights", None),
    "airlines": (
        "COUNT(DISTINCT airline_name)",
        "total_airlines",
        "airline_name IS NOT NULL AND TRIM(airline_name) != ''",
    ),
    "destinations": (
        "COUNT(DISTINCT location_city_en)",
        "total_destinations",
        "location_city_en IS NOT NULL AND TRIM(location_city_en) != ''",
    ),
}

_DIRECTION = {"departures": "D", "arrivals": "A"}


def count_entities(intent: dict) -> tuple[list[str], list[dict]]:
    """
    "How many departures were there at TLV?" — one number, matching the dashboard.

    Counts had no handler, so they were swallowed by `overall`, which ignores the question and
    returns airlines ranked by on-time % (LIMIT 10). The format LLM then summed those ten rows
    into "7,553 departures" against a true 79,412. A headline count is exactly the kind of number
    that must not be improvised: it appears elsewhere on the page, so it gets a reviewed query.

    Scoping rules come from stats.py, not from taste:
      - airlines/destinations are DEPARTURES-scoped (what the bar shows), unless asked otherwise
      - unqualified "how many flights" is every row, the bar's `total`
      - no time filter anywhere -- a departure scheduled for next week is counted, as on the bar
    """
    # No default. `count_of or "flights"` looked harmless and was the worst line in this file: it
    # turned every "how many X" the interpreter could not map into a flight count wearing X's
    # label -- "בנתב"ג עברו 158,434 טיסות" for passengers, "לאל על יש 0 קבצים" for files. Both had
    # been honest hedges before. An unnamed countable is a question we cannot answer, not a
    # question about flights.
    countable = (intent.get("count_of") or "").strip().lower()
    if countable not in _COUNTABLE:
        raise NoQueryHandlerMatch(f"nothing countable named: {countable or '<unset>'}")

    aggregate, alias, not_blank = _COUNTABLE[countable]
    params: dict[str, Any] = {}
    where: list[str] = []

    direction = (intent.get("direction") or "").strip().lower()
    if direction in _DIRECTION:
        where.append(f"direction = '{_DIRECTION[direction]}'")
    elif countable != "flights":
        where.append("direction = 'D'")

    if not_blank:
        where.append(not_blank)

    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params, intent.get("destination_kind") or "city"))

    airlines = intent.get("airlines") or []
    if airlines:
        params["airline"] = f"%{airlines[0].strip()}%"
        where.append("airline_name ILIKE :airline")

    clause = f" WHERE {' AND '.join(where)}" if where else ""
    # No GROUP BY and no HAVING: the min-10 rule suppresses noisy per-airline percentages, and
    # applying it to a total would quietly discard every small carrier from the count.
    return _run(f"SELECT {aggregate} AS {alias} FROM flights{clause}", params)


def rank_airlines(intent: dict) -> tuple[list[str], list[dict], dict]:
    params: dict[str, Any] = {"lim": _limit(intent)}
    where = ["direction = 'D'"]
    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params, intent.get("destination_kind") or "city"))
    order_sql, phrase = _ordering(intent)
    where_sql = " AND ".join(where)
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {where_sql}
        GROUP BY airline_name HAVING COUNT(*) >= {_MIN_SAMPLE}
        {order_sql}
        LIMIT :lim
    """
    return _ranked(sql, params, intent, phrase, "airline_name", where_sql)


def single_airline(intent: dict) -> tuple[list[str], list[dict]]:
    airlines = intent.get("airlines") or []
    if not airlines:
        raise NoQueryHandlerMatch("single_airline needs an airline")
    params: dict[str, Any] = {"airline": f"%{airlines[0].strip()}%"}
    where = ["direction = 'D'", "airline_name ILIKE :airline"]
    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params, intent.get("destination_kind") or "city"))
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {' AND '.join(where)}
        GROUP BY airline_name HAVING COUNT(*) >= 10
    """
    return _run(sql, params)


def head_to_head(intent: dict) -> tuple[list[str], list[dict], dict]:
    airlines = intent.get("airlines") or []
    if len(airlines) < 2:
        raise NoQueryHandlerMatch("head_to_head needs two airlines")
    params: dict[str, Any] = {"airlines": [f"%{a.strip()}%" for a in airlines[:2]]}
    where = ["direction = 'D'", "airline_name ILIKE ANY(:airlines)"]
    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params, intent.get("destination_kind") or "city"))
    order_sql, phrase = _ordering(intent)
    where_sql = " AND ".join(where)
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {where_sql}
        GROUP BY airline_name HAVING COUNT(*) >= {_MIN_SAMPLE}
        {order_sql}
    """
    return _ranked(sql, params, intent, phrase, "airline_name", where_sql)


def by_destination(intent: dict) -> tuple[list[str], list[dict], dict]:
    airlines = intent.get("airlines") or []
    if not airlines:
        raise NoQueryHandlerMatch("by_destination needs an airline")
    params: dict[str, Any] = {"airline": f"%{airlines[0].strip()}%", "lim": _limit(intent)}
    order_sql, phrase = _ordering(intent)
    where_sql = "direction = 'D' AND airline_name ILIKE :airline"
    sql = f"""
        SELECT location_city_en AS destination, {_METRICS_SELECT}
        FROM flights WHERE {where_sql}
        GROUP BY location_city_en HAVING COUNT(*) >= {_MIN_SAMPLE}
        {order_sql}
        LIMIT :lim
    """
    return _ranked(sql, params, intent, phrase, "location_city_en", where_sql)


def overall(intent: dict) -> tuple[list[str], list[dict], dict]:
    params: dict[str, Any] = {"lim": _limit(intent)}
    order_sql, phrase = _ordering(intent)
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE direction = 'D'
        GROUP BY airline_name HAVING COUNT(*) >= {_MIN_SAMPLE}
        {order_sql}
        LIMIT :lim
    """
    return _ranked(sql, params, intent, phrase, "airline_name", "direction = 'D'")


def by_region(intent: dict) -> tuple[list[str], list[dict], dict]:
    region = (intent.get("region") or "").strip().lower()
    countries = _REGIONS.get(region)
    if not countries:
        raise NoQueryHandlerMatch(f"unknown region: {region}")
    params: dict[str, Any] = {"countries": countries, "lim": _limit(intent)}
    order_sql, phrase = _ordering(intent)
    where_sql = "direction = 'D' AND country_en = ANY(:countries)"
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {where_sql}
        GROUP BY airline_name HAVING COUNT(*) >= {_MIN_SAMPLE}
        {order_sql}
        LIMIT :lim
    """
    return _ranked(sql, params, intent, phrase, "airline_name", where_sql)


_RECOVERY_BUCKETS = {"never_returned", "partial", "recovered", "expanded"}


def carrier_recovery(intent: dict) -> tuple[list[str], list[dict]]:
    """
    "Which airlines haven't come back yet?" — answered from the same computation as the /recovery
    page, never re-implemented here.

    This is the one AI-search question that no SELECT over `flights` can answer, because it is
    about ABSENCE: a carrier that stopped flying has no rows, so there is nothing for a WHERE
    clause to match. It needs a baseline (each carrier's own pre-disruption monthly average) to
    subtract the present from, which is exactly what compute_carrier_recovery builds. Before this
    handler existed the question fell through to the generated-SQL fallback, which produced valid
    SQL that matched nothing and answered "no data found".

    Uses the read-only engine like every other AI-search query — the LLM path never gets a
    read-write session.
    """
    bucket = (intent.get("recovery_bucket") or "never_returned").strip().lower()
    if bucket not in _RECOVERY_BUCKETS:
        bucket = "never_returned"

    with sessionmaker(bind=get_ro_engine())() as db:
        data = compute_carrier_recovery(db)

    if not data.get("crisis_window"):
        # No disruption detectable in the current data — there is no "came back" to report, and a
        # list built off an invented cutoff would look authoritative while meaning nothing.
        raise NoQueryHandlerMatch("no disruption window in the data")

    rows = [
        {
            "airline_name": c["airline_name"],
            "baseline_monthly": c["baseline_monthly"],
            "last30_flights": c["last30_flights"],
            "recovery_pct": c["recovery_pct"],
            "return_date": c["return_date"],
        }
        for c in data["carriers"]
        if c["bucket"] == bucket
    ]
    # Biggest carriers first: "British Airways hasn't come back" is the answer, "a charter
    # operator with 60 baseline flights hasn't" is trivia.
    rows.sort(key=lambda r: r["baseline_monthly"] or 0, reverse=True)
    rows = rows[: _limit(intent)]

    columns = ["airline_name", "baseline_monthly", "last30_flights", "recovery_pct", "return_date"]
    return columns, rows


_HANDLERS = {
    "count": count_entities,
    "carrier_recovery": carrier_recovery,
    "rank_airlines": rank_airlines,
    "single_airline": single_airline,
    "head_to_head": head_to_head,
    "by_destination": by_destination,
    "overall": overall,
    "by_region": by_region,
}


def run_query_handler(intent: dict) -> tuple[list[str], list[dict], dict]:
    """
    Route an intent to its handler. Raises NoQueryHandlerMatch if none applies.

    Handlers that rank return metadata describing the ranking; the rest return none, and get an
    empty dict. The caller always receives three values, so the format step never has to guess
    whether a description of the rows was available.
    """
    fn = _HANDLERS.get(intent.get("intent"))
    if fn is None:
        raise NoQueryHandlerMatch(f"no query handler for intent: {intent.get('intent')}")
    result = fn(intent)
    return result if len(result) == 3 else (result[0], result[1], {})
