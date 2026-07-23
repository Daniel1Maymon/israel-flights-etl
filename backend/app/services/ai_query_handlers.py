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

from app.config import settings
from app.services.ai_db import run_readonly

# Common metric projection reused by every handler.
_METRICS_SELECT = """
    COUNT(*) AS total_flights,
    ROUND(100.0 * SUM(CASE WHEN delay_minutes <= 15 THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct,
    ROUND(100.0 * SUM(CASE WHEN status_en ILIKE 'CANCELED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS cancel_pct,
    ROUND(AVG(CASE WHEN delay_minutes > 0 THEN delay_minutes END), 1) AS avg_delay_minutes
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


def _order_clause(metric: str, sort: str | None) -> str:
    if metric not in _METRIC:
        metric = "on_time"
    col, default_dir = _METRIC[metric]
    direction = default_dir
    if sort in ("asc", "desc"):
        direction = sort.upper()
    return f"ORDER BY {col} {direction} NULLS LAST"


def _limit(intent: dict) -> int:
    try:
        n = int(intent.get("limit") or 10)
    except (TypeError, ValueError):
        n = 10
    return max(1, min(n, settings.ai_max_rows))


def _dest_clause(destination: str, params: dict) -> str:
    """Match a destination across city (HE+EN) and country, so 'London' or 'Greece' both work."""
    params["dest"] = f"%{destination.strip()}%"
    return (
        "(location_he ILIKE :dest OR location_city_en ILIKE :dest "
        "OR location_en ILIKE :dest OR country_en ILIKE :dest)"
    )


def _run(sql: str, params: dict) -> tuple[list[str], list[dict]]:
    return run_readonly(sql, params)


def rank_airlines(intent: dict) -> tuple[list[str], list[dict]]:
    params: dict[str, Any] = {"lim": _limit(intent)}
    where = ["direction = 'D'"]
    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params))
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {' AND '.join(where)}
        GROUP BY airline_name HAVING COUNT(*) >= 10
        {_order_clause(intent.get('metric', 'on_time'), intent.get('sort'))}
        LIMIT :lim
    """
    return _run(sql, params)


def single_airline(intent: dict) -> tuple[list[str], list[dict]]:
    airlines = intent.get("airlines") or []
    if not airlines:
        raise NoQueryHandlerMatch("single_airline needs an airline")
    params: dict[str, Any] = {"airline": f"%{airlines[0].strip()}%"}
    where = ["direction = 'D'", "airline_name ILIKE :airline"]
    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params))
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {' AND '.join(where)}
        GROUP BY airline_name HAVING COUNT(*) >= 10
    """
    return _run(sql, params)


def head_to_head(intent: dict) -> tuple[list[str], list[dict]]:
    airlines = intent.get("airlines") or []
    if len(airlines) < 2:
        raise NoQueryHandlerMatch("head_to_head needs two airlines")
    params: dict[str, Any] = {"airlines": [f"%{a.strip()}%" for a in airlines[:2]]}
    where = ["direction = 'D'", "airline_name ILIKE ANY(:airlines)"]
    dest = intent.get("destination")
    if dest:
        where.append(_dest_clause(dest, params))
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE {' AND '.join(where)}
        GROUP BY airline_name HAVING COUNT(*) >= 10
        {_order_clause(intent.get('metric', 'on_time'), intent.get('sort'))}
    """
    return _run(sql, params)


def by_destination(intent: dict) -> tuple[list[str], list[dict]]:
    airlines = intent.get("airlines") or []
    if not airlines:
        raise NoQueryHandlerMatch("by_destination needs an airline")
    params: dict[str, Any] = {"airline": f"%{airlines[0].strip()}%", "lim": _limit(intent)}
    sql = f"""
        SELECT location_city_en AS destination, {_METRICS_SELECT}
        FROM flights WHERE direction = 'D' AND airline_name ILIKE :airline
        GROUP BY location_city_en HAVING COUNT(*) >= 10
        {_order_clause(intent.get('metric', 'on_time'), intent.get('sort'))}
        LIMIT :lim
    """
    return _run(sql, params)


def overall(intent: dict) -> tuple[list[str], list[dict]]:
    params: dict[str, Any] = {"lim": _limit(intent)}
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE direction = 'D'
        GROUP BY airline_name HAVING COUNT(*) >= 10
        {_order_clause(intent.get('metric', 'on_time'), intent.get('sort'))}
        LIMIT :lim
    """
    return _run(sql, params)


def by_region(intent: dict) -> tuple[list[str], list[dict]]:
    region = (intent.get("region") or "").strip().lower()
    countries = _REGIONS.get(region)
    if not countries:
        raise NoQueryHandlerMatch(f"unknown region: {region}")
    params: dict[str, Any] = {"countries": countries, "lim": _limit(intent)}
    sql = f"""
        SELECT airline_name, {_METRICS_SELECT}
        FROM flights WHERE direction = 'D' AND country_en = ANY(:countries)
        GROUP BY airline_name HAVING COUNT(*) >= 10
        {_order_clause(intent.get('metric', 'on_time'), intent.get('sort'))}
        LIMIT :lim
    """
    return _run(sql, params)


_HANDLERS = {
    "rank_airlines": rank_airlines,
    "single_airline": single_airline,
    "head_to_head": head_to_head,
    "by_destination": by_destination,
    "overall": overall,
    "by_region": by_region,
}


def run_query_handler(intent: dict) -> tuple[list[str], list[dict]]:
    """Route an intent to its handler. Raises NoQueryHandlerMatch if none applies."""
    fn = _HANDLERS.get(intent.get("intent"))
    if fn is None:
        raise NoQueryHandlerMatch(f"no query handler for intent: {intent.get('intent')}")
    return fn(intent)
