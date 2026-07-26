"""
refusal_text.py — the words a user sees when we have no answer for them.

Every refusal now carries an answer string instead of a null. Two reasons this lives in the
backend rather than the client (where the text used to be built from `reason`):

  1. A null `answer` made the analytics row lie. ai_events stores what the user saw, so a refusal
     recorded as "(no answer)" reads as though the user got a blank screen — when in fact they were
     shown a message. Reviewing traffic in the admin dashboard was guesswork.
  2. One text, one place. The client rendered its own wording per reason; nothing kept those in
     sync with what the backend actually did.

Anything that means "we have no data for that" — off-domain, unsupported, empty result, internal
error — gets the SAME generic answer, deliberately: the distinction matters for our metrics
(`reason` still records it), not to the person asking. Only the two operational refusals (daily
limit, budget) say something different, because there the user's next step is different.
"""
from __future__ import annotations

import re

_HEBREW = re.compile(r"[֐-׿]")

# The generic "we can't answer that" reply, for every reason that boils down to no relevant data.
_GENERIC = {
    "en": "I don't have data that answers that. You can ask about flights at Ben Gurion — "
          "airlines, punctuality, delays, cancellations and destinations.",
    "he": "אין לי נתונים שעונים על השאלה הזו. אפשר לשאול על טיסות בנתב\"ג — "
          "חברות תעופה, דיוק בזמנים, עיכובים, ביטולים ויעדים.",
}

_OPERATIONAL = {
    "limit": {
        "en": "You've reached today's question limit. Please try again tomorrow.",
        "he": "הגעת למכסת השאלות היומית. אפשר לנסות שוב מחר.",
    },
    "budget": {
        "en": "AI search is busy right now — please try again later, or use the destination search.",
        "he": "חיפוש ה-AI עמוס כרגע — נסו שוב מאוחר יותר, או השתמשו בחיפוש היעדים.",
    },
}


def question_language(question: str) -> str:
    """'he' if the question contains Hebrew characters, else 'en'. Matches how people actually type."""
    return "he" if _HEBREW.search(question or "") else "en"


def refusal_answer(reason: str | None, question: str) -> str:
    """The message shown to the user for a refusal, in the language they asked in."""
    lang = question_language(question)
    table = _OPERATIONAL.get(reason or "")
    return (table or _GENERIC)[lang]
