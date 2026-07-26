# AI Search — probe findings (2026-07-25)

Evidence base for hardening the natural-language search. 57 prompts × 2 runs through the real
`answer_question` pipeline (same code the endpoint calls, prod read-only DB, Gemini 2.5 Flash);
only the endpoint's cost guards were bypassed. 120k tokens, 0 crashes.

- Harness: `backend/scripts/ai_probe.py` (+ `ai_probe_prompts.json`)
- Raw records: `backend/scripts/ai_probe_results/20260725-145343-full.{jsonl,md}` — per prompt:
  parsed Intent, path taken, fallback SQL, columns, rows, prose answer, tokens, latency.

Re-run: `./venv/bin/python scripts/ai_probe.py --repeat 2 --workers 3 --tag <tag>`

---

## The reported failure

"איזו חברה טסה לארץ לעולם לא" answered with a top-airlines-by-volume table. **Locally it no longer
does** — it now routes to `carrier_recovery` and answers correctly (neg-01, both runs).

The difference is deploy drift: `carrier_recovery` exists only in the working tree
(`backend/app/services/carrier_recovery.py` is untracked, `ai_query_handlers.py` modified but not
committed). Production is running the pre-handler code, where absence questions fall through to
`overall`/`rank_airlines` — the screenshot. **Shipping the current tree fixes the reported case.**
Everything below is what the probe found *besides* that.

---

## F1 — Unfiltered rows narrated as if they were filtered (critical)

The handlers have no time, hour or destination-count dimension, so those constraints are silently
dropped — and then `format_answer` restates the user's framing over all-time, all-airline rows.
The answer looks specific and is fabricated.

| id | prompt | what came back |
| --- | --- | --- |
| time-02 | "which flights were delayed yesterday?" | all-time per-airline averages, narrated "Yesterday, Ethiopian Airlines had the highest average delay…" |
| time-03 | "מה קרה בשבוע האחרון עם העיכובים?" | same all-time rows, "בשבוע האחרון…" |
| time-05 | "מה היה אחוז הדיוק ב-2019?" | same all-time rows, "בשנת 2019…" — the data window is 2025-09-05 → 2026-07-28, so 2019 has no rows at all |
| region-02 | "which airlines are the best to Asia?" | `rank_airlines` with **no** destination filter; global rows narrated "to Asia" |
| ops-03 | "at what hour of the day are delays worst?" | a list of airlines; "the worst average delay is 206.5 minutes for C.A.L ISRAELI CARGO" |
| ops-05 | "מה היעד הכי פופולרי מישראל?" | rows are **airlines**; answer invents "דובאי, עם 2518 טיסות של Flydubai" — destination inferred from the carrier's name |

Root cause is two-sided: `Intent` carries no time window (so `overall` runs unbounded), and
`_FORMAT_SYS` instructs the model to answer using the row numbers without ever letting it say
"these rows don't answer that question".

Handling to add: time fields on `Intent` (period / start / end) with date-filtered handlers, or
route any time-qualified question to the SQL fallback (which already handles dates well — see
time-01, ops-04); plus an explicit "insufficient rows" escape hatch in the format step.

## F2 — Counting questions answered with a top-10 list (critical)

`overall` swallows "how many…" and the formatter counts the rows it was handed.

- count-01 "כמה חברות תעופה טסות מנתב\"ג?" → **"10 חברות תעופה טסות מנתב\"ג"**. The true answer is
  104 (`COUNT(DISTINCT airline_name)`, departures).
- count-02 "how many destinations can I fly to from TLV?" → "I cannot answer… I can tell you that
  SKYUP MALTA had 19 total flights" (honest, but useless; the answer is 184 cities)
- count-03 "כמה טיסות בוטלו בחודש האחרון?" → per-airline cancellation *percentages*, no count, no month
- count-04 "what is the average delay at TLV?" → three airlines' averages instead of one number

Notably `_sql_sys` already has correct COUNT DISTINCT rules — they never run, because the handler
matches first. Handling: a `count` intent (or force counting phrasings to `other`).

## F3 — Hebrew airline names never match anything (critical)

`_INTERPRET_SYS` says to keep airline names "as written", but `airline_name` in the table is
English, so every handler does `ILIKE '%אל על%'` → zero rows → `no_data`.

- single-01 "מה אחוז הדיוק של אל על?" → refused `no_data`
- h2h-02 "מי יותר טובה, אל על או ישראייר?" → refused `no_data`
- dest-01 "לאן אל על טסה הכי הרבה?" → refused `no_data`
- ambig-04 "תשווה בין אל על, אריקה, ישראייר ווויז אייר" → refused `no_data`

The same questions in English work (single-02, h2h-01, ambig-06). This is the flagship carrier
returning "no data" to Hebrew speakers — likely the most-hit bug in real traffic. Handling:
translate airline names to English in `interpret` exactly as destinations already are, backed by an
alias map (אל על → EL AL, ישראייר → ISRAIR, אריקה → ARKIA, וויז → WIZZ).

## F4 — Negation inverted into its opposite (critical)

- neg-07 "which destinations are NOT served from Ben Gurion?" → fallback SQL listing the
  destinations that **are** served, narrated as "The following 20 destinations are not served from
  Ben Gurion: Abu Dhabi, Amsterdam, …" — a confident, complete inversion. (Also unstable: the
  second run refused `unsupported`.)
- neg-08 "איזו חברה אף פעם לא מבטלת טיסות?" → "0% cancellations" carriers with 11–36 flights.

The dataset has no roster of unserved destinations, so this can only be refused, not answered.
Handling: treat "not served / never flies there" as unanswerable-by-design (the `no_data` reason
already models this honestly).

## F5 — Airport codes don't resolve (medium)

- fuzzy-02 "מי הכי טובה ל-JFK?" → `destination: "JFK"` → `no_data` (`location_en` holds
  "NEW YORK - J. F. KENNEDY")
- fuzzy-03 "כמה טיסות יש ל NYC?" → worked, because the fallback translated NYC → New York

Handling: resolve IATA codes to city names during `interpret`.

## F6 — Rankings are topped by statistical noise (medium)

`HAVING COUNT(*) >= 10` lets 11–36-flight carriers win every "best airline" question:
SKYUP MALTA (19 flights, 94.7%) is the answer to rank-01, ambig-03, ambig-05, region-02, time-05,
and C.A.L ISRAELI CARGO — a **cargo** airline — is runner-up in consumer-facing rankings.
Handling: a much higher minimum (a few hundred flights, or a percentile), and exclude cargo carriers.

## F7 — LIMIT truncation reported as a total (medium)

time-01 "אילו טיסות יוצאות מחר?" → SQL `LIMIT 50` returned 50 rows, `format_answer` sees only
`rows[:20]`, answer opens "מחר… מתוכננות 20 טיסות". Any capped result can be narrated as a count.
Handling: pass the real row count to the format step and forbid counting the sample.

## F8 — Same input, different resolution (medium)

At `temperature=0`, across two identical runs:

- neg-07 → `other`/fallback vs refused `unsupported`
- region-01 "אילו חברות הכי דייקניות באירופה?" → `by_region` vs `rank_airlines`

So single-run behaviour can't be trusted as "the" behaviour — the probe defaults to `--repeat 2`
for this reason. Anything relying on stable routing needs a deterministic pre-classifier or
handler-level tolerance.

## F9 — Adjacent-but-absent topics answered with punctuality (low)

ambig-06 "is it safe to fly with El Al?" → on-time and cancellation stats, no caveat that the data
says nothing about safety. ambig-03 "הכי טוב" (two bare words) → a full on-time ranking.

---

## What already works well

- **Off-domain and injection: 5/5 refused** — recipes, "ignore previous instructions", `DROP TABLE`,
  ticket prices (correctly out of scope: no price data), "which LLM are you". Plus gibberish
  (ambig-02) and one-word input (ambig-01).
- **Honest emptiness** — genuinely absent carriers/destinations return `no_data` rather than a
  narrated guess: Ryanair (nodata-01), Pyongyang (nodata-02), Tehran (nodata-03, "אין טיסות לטהרן").
- **The SQL fallback is the strong path** — count-05 (157,546 flights), ops-01 (Terminal 3,
  147,851), ops-04 (191 landings today), time-01 (tomorrow's departures), fuzzy-03 (NYC), time-04
  (seasonal comparison, correctly noting winter is missing from the window). Handler shortcuts are
  where the wrong answers come from, not the generated SQL.
- **English ranking / single-airline / head-to-head** paths behave as designed, and typos survive
  (fuzzy-01 "wich airlin is best to lodnon" → correct London ranking).

## Suggested order of work

1. Ship the working tree (fixes the reported case) — F9/deploy drift.
2. F3 Hebrew airline names — highest real-traffic impact, smallest change (prompt + alias map).
3. F1 + F2 — stop handlers from silently dropping time and count dimensions; let the fallback take them.
4. F4 negation → explicit refusal; F7 count-vs-sample; F6 sample threshold.
5. F5, F8, F9 as follow-ups.
