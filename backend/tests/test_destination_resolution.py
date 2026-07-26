"""
A destination the user names must be resolved to a value that exists in `flights` before any
aggregate runs.

THE TWO BUGS THIS CLOSES — same cause, opposite symptoms
    `_dest_clause` wildcard-matched the user's raw text against location_he / location_city_en /
    location_en / country_en. Nothing checked the entity was real, so:

      wrong refusal   "עם איזו חברה לטוס לכריתים"  -> ILIKE '%כרתים%' matches nothing, because the
                      data stores the AIRPORT (HERAKLION / הרקליון), not the island. 1,092 flights
                      exist; the user was told there was no data and invited to ask about
                      destinations -- the thing that had just failed.
      fabrication     "איזה חברות טסות ליונתן גיי"  -> the filter contributed nothing, the aggregate
                      ran unfiltered, and 22 real airlines were presented as flying to a place that
                      does not exist.

    No string operation fixes the first: "Crete" and "HERAKLION" share no substring, because the
    relationship is geographic, not orthographic. Resolution against the real vocabulary does.

LAYERS
    1. unit  — resolution logic against a fixture vocabulary (always runs)
    2. db    — the vocabulary really contains what we claim (needs DATABASE_URL_RO)
    3. live  — the LLM step for aliases plain matching can't reach (needs the key; run with -m llm)
"""
from __future__ import annotations

import os

import pytest

from app.services import destination_resolver as DR

needs_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL_RO"), reason="DATABASE_URL_RO not set")
needs_llm = pytest.mark.skipif(
    not (os.getenv("DATABASE_URL_RO") and os.getenv("GEMINI_API_KEY")),
    reason="live LLM test")

LIVE_REPEATS = int(os.getenv("AI_LIVE_REPEATS", "3"))

# A stand-in for what the DB returns, small enough to reason about.
FIXTURE = DR.Vocabulary(
    cities=["ATHENS", "HERAKLION", "LONDON", "NEW YORK", "RHODES"],
    countries=["GREECE", "UNITED KINGDOM", "USA"],
    aliases={
        "athens": ("city", "ATHENS"), "אתונה": ("city", "ATHENS"),
        "heraklion": ("city", "HERAKLION"), "הרקליון": ("city", "HERAKLION"),
        "london": ("city", "LONDON"), "לונדון": ("city", "LONDON"),
        "new york": ("city", "NEW YORK"),
        "rhodes": ("city", "RHODES"), "רודוס": ("city", "RHODES"),
        "greece": ("country", "GREECE"), "יוון": ("country", "GREECE"),
        "united kingdom": ("country", "UNITED KINGDOM"),
        "usa": ("country", "USA"),
    },
)


# --- layer 1: resolution logic ---------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("ATHENS", ("city", "ATHENS")),
    ("athens", ("city", "ATHENS")),
    ("  Athens  ", ("city", "ATHENS")),
    ("אתונה", ("city", "ATHENS")),
    ("Greece", ("country", "GREECE")),
    ("יוון", ("country", "GREECE")),
    ("New York", ("city", "NEW YORK")),
])
def test_direct_matches_need_no_llm(raw, expected):
    """The common case must cost zero extra tokens."""
    called = []
    assert DR.resolve(raw, FIXTURE, ask_llm=lambda *a: (called.append(a), 0)[1:])[0] == expected
    assert not called, "a name already in the vocabulary must not trigger an LLM call"


@pytest.mark.parametrize("raw,expected", [
    ("ליוון", ("country", "GREECE")),      # 'to Greece'
    ("בלונדון", ("city", "LONDON")),        # 'in London'
    ("מאתונה", ("city", "ATHENS")),         # 'from Athens'
])
def test_hebrew_prefixes_are_stripped(raw, expected):
    """ל/ב/מ/ה fuse onto the noun in Hebrew; the interpreter does not always strip them."""
    assert DR.resolve(raw, FIXTURE, ask_llm=lambda *a: (None, 0))[0] == expected


def test_unknown_place_asks_the_llm_and_accepts_a_vocabulary_answer():
    """Crete: no shared substring with HERAKLION, so only the LLM step can bridge it."""
    asked = []

    def ask(raw, candidates):
        asked.append(raw)
        assert "HERAKLION" in candidates, "the model must be shown the real vocabulary"
        return "HERAKLION", 847

    assert DR.resolve("Crete", FIXTURE, ask_llm=ask)[0] == ("city", "HERAKLION")
    assert asked == ["Crete"]


@pytest.mark.parametrize("answer, resolves, why", [
    ("HERAKLION", True, "a name from the vocabulary"),
    ("ATLANTIS", False, "a name the model invented"),
    ("NONE", False, "the model declining"),
])
def test_the_resolver_reports_the_tokens_it_spent(answer, resolves, why):
    """
    These tokens used to be dropped, and dropped tokens are spent twice over: the monthly budget
    kill-switch counted lower than the real bill, so it tripped late, and the dashboard's cost
    figure understated what the feature actually costs.

    Reported on failure too — a model that answers NONE, or invents a place, has still been paid
    for. Billing does not care whether we could use the answer.
    """
    resolved, tokens = DR.resolve("Crete", FIXTURE, ask_llm=lambda *a: (answer, 847))
    assert tokens == 847, why
    assert (resolved is not None) is resolves


def test_a_directly_matched_destination_costs_nothing():
    """The common path never calls a model, so it must never report tokens."""
    assert DR.resolve("Athens", FIXTURE, ask_llm=lambda *a: ("ATHENS", 999)) == (("city", "ATHENS"), 0)


def test_llm_answer_outside_the_vocabulary_is_rejected():
    """The guarantee: the model can pick from the data, it cannot invent."""
    assert DR.resolve("Crete", FIXTURE, ask_llm=lambda *a: ("ATLANTIS", 91))[0] is None


@pytest.mark.parametrize("junk", ["יונתן גיי", "רקטום של יונתן", "Wakanda", "asdfgh"])
def test_nonexistent_places_resolve_to_nothing(junk):
    """The fabrication bug: unresolvable must mean unresolvable, never 'match everything'."""
    assert DR.resolve(junk, FIXTURE, ask_llm=lambda *a: ("NONE", 88))[0] is None


def test_llm_declining_is_honoured():
    assert DR.resolve("somewhere", FIXTURE, ask_llm=lambda *a: ("NONE", 88))[0] is None
    assert DR.resolve("somewhere", FIXTURE, ask_llm=lambda *a: ("", 12))[0] is None
    assert DR.resolve("somewhere", FIXTURE, ask_llm=lambda *a: (None, 0))[0] is None


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_input_resolves_to_nothing(raw):
    assert DR.resolve(raw, FIXTURE, ask_llm=lambda *a: ("ATHENS", 40))[0] is None


def test_short_fragments_do_not_substring_match():
    """'NY' must not silently become NEW YORK -- over-matching is how the old wildcard failed."""
    assert DR.resolve("NY", FIXTURE, ask_llm=lambda *a: ("NONE", 88))[0] is None


def test_llm_failure_does_not_break_the_request():
    def boom(raw, candidates):
        raise RuntimeError("provider down")

    assert DR.resolve("Crete", FIXTURE, ask_llm=boom)[0] is None


# --- layer 2: the real vocabulary --------------------------------------------------------------

@needs_db
def test_vocabulary_loads_from_the_data():
    v = DR.get_vocabulary()
    assert len(v.cities) > 150 and len(v.countries) > 40
    assert "HERAKLION" in v.cities and "ATHENS" in v.cities
    assert "GREECE" in v.countries


@needs_db
def test_vocabulary_carries_the_hebrew_names():
    v = DR.get_vocabulary()
    assert v.aliases.get("הרקליון") == ("city", "HERAKLION")
    assert v.aliases.get("אתונה") == ("city", "ATHENS")


@needs_db
def test_vocabulary_is_cached():
    DR._vocab_cache = None
    calls = []
    real = DR.run_readonly

    def counting(sql, params=None):
        calls.append(sql)
        return real(sql, params)

    DR.run_readonly = counting
    try:
        DR.get_vocabulary()
        DR.get_vocabulary()
        assert len(calls) == 1, "the vocabulary query must not run per request"
    finally:
        DR.run_readonly = real


# --- layer 3: end to end, repeated -------------------------------------------------------------

@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_crete_resolves_to_heraklion(run):
    assert DR.resolve("Crete", DR.get_vocabulary())[0] == ("city", "HERAKLION")
    assert DR.resolve("כרתים", DR.get_vocabulary())[0] == ("city", "HERAKLION")


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_the_crete_question_now_answers_with_real_flights(run):
    """The prompt from production that was refused while 1,092 flights existed."""
    from app.services.ai_db import run_readonly
    from app.services.ai_search import answer_question

    _, truth = run_readonly(
        "SELECT COUNT(*) n FROM flights WHERE direction='D' AND location_city_en='HERAKLION'")
    assert truth[0]["n"] > 500, "fixture assumption: Crete is well represented"

    resp, _ = answer_question("עם איזו חברה לטוס לכריתים")
    assert not resp.refused, f"still refused: {resp.reason}"
    assert resp.rows, "must return airlines flying to Heraklion"


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("question", [
    "איזה חברות תעופה טסות מנתבג ליונתן גיי?",
    "איזה חברות טסות מנתבג לרקטוםשליונתן",
])
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_invented_destinations_are_still_refused(question, run):
    """The fix must not reopen the fabrication hole it also closes."""
    from app.services.ai_search import answer_question

    resp, _ = answer_question(question)
    assert resp.refused and resp.reason in ("no_data", "off_domain"), \
        f"invented destination answered: {resp.answer}"


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("question,city", [
    ("which airline is most punctual to London?", "LONDON"),
    ("מי הכי מדוייקת לאתונה?", "ATHENS"),
])
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_destinations_that_already_worked_still_work(question, city, run):
    from app.services.ai_search import answer_question

    resp, _ = answer_question(question)
    assert not resp.refused and resp.rows, f"regression on {city}: {resp.reason}"
