"""
destination_resolver.py — turn a place the user named into a value that exists in `flights`.

Before this existed, a destination went straight into a wildcard `ILIKE '%<user text>%'` across
four columns. That fails in both directions:

  * a REAL place the data stores under another name matched nothing — the island כרתים is filed
    under its airport, HERAKLION, and the two share no substring, so 1,092 flights were reported
    as "no data";
  * an INVENTED place also matched nothing, but the filter simply contributed no rows to the
    WHERE clause, the aggregate ran unfiltered, and 22 real airlines were presented as serving a
    destination that does not exist.

Resolution fixes both because it asks one question the old code never asked: does this entity
correspond to anything we hold? A name that resolves is queried by its canonical value; a name
that does not is a refusal, not an unfiltered query.

Two stages, cheapest first:

  1. Direct lookup against the vocabulary built from the data (English city, Hebrew name, country
     in both languages). Covers Athens/London/Greece and every name the user types as stored —
     the overwhelming majority — at zero token cost.
  2. Only when that fails, one small LLM call that must pick from the real vocabulary. This is the
     step that bridges Crete → HERAKLION, which is a geographic relationship no string comparison
     can discover. Its answer is validated against the vocabulary, so the model can choose from
     the data but can never invent.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import structlog

from app.services.ai_db import run_readonly

logger = structlog.get_logger()

# Hebrew fuses single-letter prepositions onto the noun ("ליוון" = to Greece), and the interpreter
# does not reliably strip them. Only tried after the whole string fails, so a real name beginning
# with one of these letters is never mangled.
_HE_PREFIXES = ("ל", "ב", "מ", "ה", "כ")

# Below this, a substring comparison stops being evidence: "NY" is inside "GERMANY".
_MIN_FRAGMENT = 4

Resolved = Optional[tuple[str, str]]   # ("city" | "country", CANONICAL VALUE)


@dataclass
class Vocabulary:
    """Every destination the data actually contains, plus the names users type for them."""
    cities: list[str]
    countries: list[str]
    aliases: dict[str, tuple[str, str]] = field(default_factory=dict)

    def candidates(self) -> list[str]:
        return self.cities + self.countries


_VOCAB_TTL_SECONDS = 3600.0
_vocab_cache: Optional[tuple[float, Vocabulary]] = None


def get_vocabulary() -> Vocabulary:
    """
    Build the destination vocabulary from `flights`, cached for an hour.

    Derived from the data rather than hand-maintained, so a destination the ETL adds tomorrow is
    resolvable the day it lands — which is the whole reason not to keep an alias table.
    """
    global _vocab_cache
    now = time.monotonic()
    if _vocab_cache and now - _vocab_cache[0] < _VOCAB_TTL_SECONDS:
        return _vocab_cache[1]

    _, rows = run_readonly("""
        SELECT DISTINCT location_city_en, location_he, country_en, country_he
        FROM flights
        WHERE direction = 'D' AND location_city_en IS NOT NULL AND TRIM(location_city_en) != ''
    """)

    cities: set[str] = set()
    countries: set[str] = set()
    aliases: dict[str, tuple[str, str]] = {}

    for r in rows:
        city, country = r["location_city_en"], r["country_en"]
        if city:
            cities.add(city)
            aliases[city.strip().lower()] = ("city", city)
            if r["location_he"]:
                aliases[r["location_he"].strip().lower()] = ("city", city)
        if country:
            countries.add(country)
            aliases[country.strip().lower()] = ("country", country)
            if r["country_he"]:
                aliases[r["country_he"].strip().lower()] = ("country", country)

    vocab = Vocabulary(cities=sorted(cities), countries=sorted(countries), aliases=aliases)
    _vocab_cache = (now, vocab)
    return vocab


def _direct(key: str, vocab: Vocabulary) -> Resolved:
    """Exact alias, then a containment check long enough to mean something."""
    if key in vocab.aliases:
        return vocab.aliases[key]
    if len(key) >= _MIN_FRAGMENT:
        for alias, target in vocab.aliases.items():
            if len(alias) >= _MIN_FRAGMENT and (key in alias or alias in key):
                return target
    return None


def _ask_llm_default(raw: str, candidates: list[str]) -> tuple[Optional[str], int]:
    """Imported lazily: the resolver is used by tests that must not need a provider key."""
    from app.services.llm_tasks import LLMTasks

    return LLMTasks().resolve_destination(raw, candidates)


def resolve(
    raw: Optional[str],
    vocab: Vocabulary,
    ask_llm: Callable[[str, list[str]], tuple[Optional[str], int]] = _ask_llm_default,
) -> tuple[Resolved, int]:
    """
    Resolve a user-supplied place to ("city"|"country", canonical), or None if it isn't in the data.

    None is a real answer, not an error: it means the caller must refuse rather than run an
    unfiltered aggregate. That distinction is the fabrication fix.

    Returns (resolution, tokens_spent), matching every other LLM step in the codebase — interpret,
    generate_sql and format_answer all hand their token count back so the caller can meter it.
    This one used to return the answer alone and drop the count on the floor, which made those
    tokens invisible to BOTH cost controls: they never reached ai_budget, so the monthly kill
    switch tripped late, and they never reached the dashboard, so the cost shown there was under
    the real spend. The direct path (the overwhelming majority of questions) still returns 0
    because it never calls a model.

    Tokens are reported even when the resolution FAILS. A model that answers NONE, or names
    something outside the vocabulary, has still been paid for.
    """
    key = (raw or "").strip().lower()
    if not key:
        return None, 0

    hit = _direct(key, vocab)
    if hit:
        return hit, 0

    # "ליוון" -> "יוון". Tried only after the full string fails.
    if len(key) > 2 and key[0] in _HE_PREFIXES:
        hit = _direct(key[1:], vocab)
        if hit:
            return hit, 0

    try:
        answer, tokens = ask_llm(raw, vocab.candidates())
    except Exception as e:
        # A resolver outage must not turn into a wrong answer; unresolved means refuse. The token
        # count is unknowable here -- the call raised, so nothing reported one.
        logger.warning("destination resolution failed", place=raw, error=str(e))
        return None, 0

    if not answer or answer.strip().upper() == "NONE":
        return None, tokens

    # The model may choose from the data; it may not invent. Anything outside the vocabulary is
    # discarded, which is what stops "יונתן גיי" from acquiring an airport.
    return vocab.aliases.get(answer.strip().lower()), tokens
