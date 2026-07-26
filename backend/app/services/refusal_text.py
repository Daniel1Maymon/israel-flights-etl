"""
refusal_text.py — the words a user sees when we have no answer for them.

Every refusal now carries an answer string instead of a null. Two reasons this lives in the
backend rather than the client (where the text used to be built from `reason`):

  1. A null `answer` made the analytics row lie. ai_events stores what the user saw, so a refusal
     recorded as "(no answer)" reads as though the user got a blank screen — when in fact they were
     shown a message. Reviewing traffic in the admin dashboard was guesswork.
  2. One text, one place. The client rendered its own wording per reason; nothing kept those in
     sync with what the backend actually did.

A user can be shown an answer built from the data, or one of two sentences below.

The default is the generic one, and nearly every refusal takes it — off-domain, unsupported, empty
result, budget, internal error alike. Those differ in ways that matter to our metrics (`reason`
records which) and not to the person asking; telling a visitor "unsupported" rather than "no data"
gives them nothing to do differently.

The daily cap is the exception, because there the user's next step IS different: the data they
asked for exists and they will get it tomorrow. Under the generic wording a capped visitor reads
"I don't have data that answers that" and concludes the product is empty, which is both false and
the opposite of what we want them to believe.
"""
from __future__ import annotations

import re

from app.config import settings

_HEBREW = re.compile(r"[֐-׿]")

# The one reply, in the two languages the product speaks.
_GENERIC = {
    "en": "I don't have data that answers that. You can ask about flights at Ben Gurion — "
          "airlines, punctuality, delays, cancellations and destinations.",
    "he": "אין לי נתונים שעונים על השאלה הזו. אפשר לשאול על טיסות בנתב\"ג — "
          "חברות תעופה, דיוק בזמנים, עיכובים, ביטולים ויעדים.",
}


def question_language(question: str) -> str:
    """'he' if the question contains Hebrew characters, else 'en'. Matches how people actually type."""
    return "he" if _HEBREW.search(question or "") else "en"


def limit_text(lang: str) -> str:
    """
    The cap notice, quoting the live setting so the number can never contradict the code.

    Hard-coding "10" here would be wrong the moment AI_DAILY_LIMIT_PER_USER is changed in an
    environment — and a user told the wrong number has been lied to about the only fact this
    message carries.
    """
    n = settings.ai_daily_limit_per_user
    if lang == "he":
        return (
            f"הגעת למכסת השאלות היומית ({n} שאלות ליום). "
            'המכסה מתאפסת מחר — אפשר לשאול שוב אז, ובינתיים להשתמש בחיפוש היעדים.'
        )
    return (
        f"You've used today's {n} questions. The limit resets tomorrow — please come back then, "
        "or use the destination search in the meantime."
    )


def refusal_answer(reason: str | None, question: str) -> str:
    """The message shown for a refusal, in the language the question was asked in."""
    lang = question_language(question)
    return limit_text(lang) if reason == "limit" else _GENERIC[lang]
