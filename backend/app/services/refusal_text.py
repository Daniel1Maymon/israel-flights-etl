"""
refusal_text.py — the words a user sees when we have no answer for them.

Every refusal now carries an answer string instead of a null. Two reasons this lives in the
backend rather than the client (where the text used to be built from `reason`):

  1. A null `answer` made the analytics row lie. ai_events stores what the user saw, so a refusal
     recorded as "(no answer)" reads as though the user got a blank screen — when in fact they were
     shown a message. Reviewing traffic in the admin dashboard was guesswork.
  2. One text, one place. The client rendered its own wording per reason; nothing kept those in
     sync with what the backend actually did.

A user can be shown an answer built from the data, or one of the three sentences below.

The default is the generic one, and the refusals about the QUESTION take it — off-domain,
unsupported, empty result. Those differ in ways that matter to our metrics (`reason` records
which) and not to the person asking; telling a visitor "unsupported" rather than "no data" gives
them nothing to do differently.

The refusals about the SYSTEM get their own words, and the test is the same every time: the user's
next step is different, so the generic sentence would actively mislead them.

  limit           the daily cap — the data exists; they get it tomorrow
  llm_off         an admin switched the feature off to hold spend down
  budget          our own monthly token ceiling tripped
  provider_quota  the provider's ceiling tripped: a spend cap, quota or rate limit
  error           something broke

Under the generic wording every one of those visitors reads "I don't have data that answers that",
concludes the product is empty, and does not come back — when nothing is wrong with the data at
all. That is not hypothetical for the last two. A Google project spend cap was hit in production,
the 429 became reason='error', and the site told users the dataset had no answer for questions it
answers perfectly well. The only record of the truth was a log line.
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


def off_text(lang: str) -> str:
    """
    The kill-switch notice — the second exception to the generic reply, for the same reason as the
    cap: the user's next step differs.

    The data exists and the feature works; an admin has turned it off to hold token spend down. A
    visitor told "I don't have data that answers that" concludes the product is empty and does not
    come back, when in fact the answer is "not now, and here is what still works".
    """
    if lang == "he":
        return (
            'הצ\'אט החכם כבוי כרגע בגלל צריכת טוקנים. הוא יחזור בקרוב — '
            'בינתיים אפשר להשתמש בחיפוש היעדים, בדירוגי חברות התעופה ובלוח הטיסות.'
        )
    return (
        "AI chat is off for now because of token usage. It'll be back soon — in the meantime you "
        "can still use the destination search, the airline rankings and the flight board."
    )


def budget_text(lang: str) -> str:
    """
    The token-ceiling notice — for OUR monthly budget and for the PROVIDER's cap alike.

    Two reasons, one sentence, because the two are one situation to a visitor: the feature is
    paused over cost and will come back on its own. Which ceiling was hit is our problem, and
    `reason` keeps them apart on the dashboard ('budget' vs 'provider_quota') so we can tell
    whether we throttled ourselves or Google did.

    Deliberately does not promise a date. The monthly budget resets with the month, a spend cap
    resets when it is raised or the billing period rolls over, and a rate limit clears in a
    minute — a specific time here would be wrong for at least two of the three.
    """
    if lang == "he":
        return (
            'הצ\'אט החכם הגיע למכסת הטוקנים שלו ומושהה כרגע. הוא יחזור כשהמכסה תתחדש — '
            'בינתיים אפשר להשתמש בחיפוש היעדים, בדירוגי חברות התעופה ובלוח הטיסות.'
        )
    return (
        "AI chat has reached its token limit and is paused for now. It'll be back when the limit "
        "resets — in the meantime you can still use the destination search, the airline rankings "
        "and the flight board."
    )


def error_text(lang: str) -> str:
    """
    The something-broke notice.

    Says the answer failed, NOT that the answer does not exist — the distinction the generic
    sentence destroyed. Retrying is worth suggesting here and nowhere else: an error may be
    transient, whereas a cap or an off switch will refuse the next question just as firmly.
    """
    if lang == "he":
        return (
            'משהו השתבש אצלנו והתשובה לא נוצרה — זו תקלה זמנית, לא חוסר בנתונים. '
            'כדאי לנסות שוב עוד רגע, ובינתיים חיפוש היעדים, דירוגי חברות התעופה ולוח '
            'הטיסות עובדים כרגיל.'
        )
    return (
        "Something went wrong on our side and the answer didn't come back — that's a temporary "
        "fault, not missing data. Please try again in a moment; the destination search, the "
        "airline rankings and the flight board are working as usual."
    )


def refusal_answer(reason: str | None, question: str) -> str:
    """The message shown for a refusal, in the language the question was asked in."""
    lang = question_language(question)
    if reason == "limit":
        return limit_text(lang)
    if reason == "llm_off":
        return off_text(lang)
    if reason in ("budget", "provider_quota"):
        return budget_text(lang)
    if reason == "error":
        return error_text(lang)
    return _GENERIC[lang]
