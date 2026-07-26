"""
refusal_text.py — the words a user sees when we have no answer for them.

Every refusal now carries an answer string instead of a null. Two reasons this lives in the
backend rather than the client (where the text used to be built from `reason`):

  1. A null `answer` made the analytics row lie. ai_events stores what the user saw, so a refusal
     recorded as "(no answer)" reads as though the user got a blank screen — when in fact they were
     shown a message. Reviewing traffic in the admin dashboard was guesswork.
  2. One text, one place. The client rendered its own wording per reason; nothing kept those in
     sync with what the backend actually did.

There are exactly two things a user can be shown: an answer built from the data, or the one string
below. Every refusal takes the same wording — off-domain, unsupported, empty result, daily limit,
budget, internal error alike. The distinction between them matters for our metrics, where `reason`
still records it, not to the person asking.
"""
from __future__ import annotations

import re

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


def refusal_answer(reason: str | None, question: str) -> str:
    """
    The message shown for any refusal, in the language the question was asked in.

    `reason` is accepted but not branched on: it stays in the signature because callers have it and
    analytics records it, and because reading `refusal_answer(reason, q)` at the call site says what
    this is for. If a reason ever needs its own wording, this is where that decision would live —
    today none does.
    """
    return _GENERIC[question_language(question)]
