"""
When the dataset cannot answer, say so — never answer the nearest question it can.

THE BUG
    The interpreter maps an unavailable concept onto an available column, and the handler happily
    serves it:
        "כמה שערים"        -> terminals            -> "בנתב\"ג יש 2 שערים"
        "כמה מסלולי המראה" -> destination count    -> "בנתב\"ג יש 186 מסלולי המראה"
        "כמה נוסעים"       -> flight count         -> "בנתב\"ג עברו 158,434 טיסות"
        "כמה קבצים"        -> flight count         -> "לאל על יש 0 קבצים"
        "הכי דניאל"        -> on-time %            -> a ranking for a metric that does not exist
    Every one is a confident sentence containing a real number that answers a question nobody
    asked. Two of them were HEDGES before the count handler shipped -- the permissive default
    `count_of or "flights"` turned "I don't have that" into a fabrication.

    The list of missing concepts can never be complete: `הכי דניאל` shows the substitution fires on
    any unrecognised word, not only on the columns we thought to enumerate. So the rule matters
    more than the list, and both are tested here.
"""
from __future__ import annotations

import os

import pytest

from app.services import ai_query_handlers as H
from app.services.ai_query_handlers import NoQueryHandlerMatch

needs_llm = pytest.mark.skipif(
    not (os.getenv("DATABASE_URL_RO") and os.getenv("GEMINI_API_KEY")),
    reason="live LLM test")
LIVE_REPEATS = int(os.getenv("AI_LIVE_REPEATS", "3"))


# --- the handler must not invent a countable ---------------------------------------------------

@pytest.mark.parametrize("count_of", [None, "", "  ", "terminals", "gates", "runways",
                                      "passengers", "seats", "files", "other", "nonsense"])
def test_unmapped_countable_is_declined(count_of):
    """No default. A count the interpreter could not name is not a flight count."""
    with pytest.raises(NoQueryHandlerMatch):
        H.count_entities({"intent": "count", "count_of": count_of})


@pytest.mark.parametrize("count_of", ["flights", "airlines", "destinations",
                                      "FLIGHTS", " destinations "])
def test_the_three_real_countables_still_work(monkeypatch, count_of):
    monkeypatch.setattr(H, "_run", lambda sql, params: (["n"], [{"n": 1}]))
    cols, rows = H.count_entities({"intent": "count", "count_of": count_of})
    assert rows == [{"n": 1}]


# --- end to end: the exact production prompts ---------------------------------------------------

UNANSWERABLE = [
    'כמה שערים יש בנתב"ג?',                    # no gate column
    'כמה מסלולי המראה יש בנתב"ג?',              # no runway column
    'כמה נוסעים עברו בנתב"ג?',                  # no passenger column
    "How many runways does Ben Gurion have?",
    "כמה קבצים ביחד לאל על יש לך",              # internal files, not data
    "כמה מושבים יש סך הכל בכל המטוסים בצי של אל על",   # no fleet data
    "מה החברה עם הביצועים הכי דניאל",            # not a metric
    "מה הטיסה הקצרה ביותר מישראל לחול?",         # no duration column
    'איך הכי זול לטוס לארה"ב?',                  # no price data
]

# Figures each substitution used to produce. None of them may appear in a refusal.
SUBSTITUTED_FIGURES = ["186", "158,434", "158434", "79,4", "794", "2 שערים", "94.7"]


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("question", UNANSWERABLE)
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_unanswerable_questions_are_refused(question, run):
    from app.services.ai_search import answer_question

    resp, _ = answer_question(question)
    assert resp.refused, f"answered an unanswerable question: {resp.answer!r}"
    assert not resp.rows


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("question", UNANSWERABLE)
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_refusals_carry_no_substituted_number(question, run):
    """A refusal that still quotes 186 has substituted and then apologised."""
    from app.services.ai_search import answer_question

    resp, _ = answer_question(question)
    text = resp.answer or ""
    leaked = [f for f in SUBSTITUTED_FIGURES if f in text]
    assert not leaked, f"refusal leaked {leaked}: {text}"


# --- the answerable neighbours must not become collateral damage --------------------------------

ANSWERABLE = [
    ('כמה המראות היו בנתב"ג?', "flights"),
    ("כמה חברות תעופה יש בנתונים?", "airlines"),
    ("כמה יעדים יש בנתונים?", "destinations"),
    ("which airline is most punctual to London?", None),
    ("עם איזו חברה לטוס לכריתים", None),
]


@needs_llm
@pytest.mark.llm
@pytest.mark.parametrize("question,_kind", ANSWERABLE)
@pytest.mark.parametrize("run", range(LIVE_REPEATS))
def test_answerable_questions_still_answer(question, _kind, run):
    """Tightening the refusal rule must not make the product refuse its own subject matter."""
    from app.services.ai_search import answer_question

    resp, _ = answer_question(question)
    assert not resp.refused, f"refused an answerable question ({resp.reason}): {question}"
    assert resp.rows
