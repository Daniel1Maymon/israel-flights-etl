# New Pages Plan — Nav Bar, Airline Performance, Insights, Recovery Tracker

Status: **steps 1–4 built and verified; steps 5–6 (`/airlines`) not started.**
Date: 2026-07-24

## Build log

| Step | State |
|---|---|
| 1. `PageLayout` + `SiteNav`, retrofitted onto Index and FlightBoard | done |
| 2. `carrier_nationality.py` + `insights_logic.py` + 47 unit tests | done |
| 3. `/api/v1/insights/*` endpoints | done, verified against production data |
| 4. `/insights` page (4 story cards) | done |
| 5. `/recovery` page | done |
| 6. `/airlines` airline analysis page + endpoints | done, verified against production data |

Plus one unplanned fix: a mobile layout pass (see "Mobile" below).

### Decisions resolved since the proposal

- **Crisis window is derived, not hardcoded** (the open question — approved). A month is flagged
  when its cancellation rate clears both a 5% floor and 3× the *calm-half* median. The trimmed
  baseline matters: using the plain median breaks down exactly when a disruption is long, because
  once crisis months are half the dataset the median is itself a crisis month, the threshold
  inflates past every real value, and the detector reports no disruption on the most disrupted
  input it will ever see. Caught by `test_longest_run_wins_over_isolated_spike`.
- **Logic lives in pure functions, SQL only aggregates.** The suite runs on SQLite, so any rule
  expressed in PostgreSQL dialect can only ever be *skipped* under test. The classification rules
  are therefore plain functions over plain dicts in `insights_logic.py`, and they genuinely run.
- **`/recovery` is a separate tab**, not a sub-tab of `/insights` (the second open question).

### Verification against production data (read-only replica, 2026-07-24)

`/monthly-by-nationality` reproduces the direct-SQL figures exactly, and the derived window comes
back as 2026-03 → 2026-04 at a 5.0% threshold. `/carrier-recovery` returns 62 carriers as
10 never returned / 18 partial / 13 recovered / 21 expanded.

All three traps confirmed handled on real data:

| Trap | Wrong answer it produced | Now |
|---|---|---|
| Georgian Airways — flew once on 2026-04-17, nothing since | bucketed as returned | `never_returned`, stale return date suppressed |
| El Al / Arkia / Israir — never stopped flying | "returned" on whatever date the query window opened | no return date; the only three carriers without one |
| Enter Air / Neos / Fly Lili — seasonal charter gaps | "returned" 2025-10-20, five months *before* the disruption | return dates constrained to on/after the crisis start |

The third was not in the original plan — it surfaced only when the endpoint ran against real data.

### Test state

- `test_insights_logic.py` — **47 passed**. Real coverage; no DB, no dialect dependency.
- `test_insights_endpoints.py` — **10 skipped** on SQLite by design, with the skip reason stated in
  the module docstring so a green run is not mistaken for coverage. Run against PostgreSQL to
  exercise them.
- Pre-existing and untouched by this work: `test_flight_board.py` fails 26 tests on a signature
  mismatch (`_build_query()` got an unexpected keyword argument 'page'), and every `client`-fixture
  test errors when the local Postgres on :5433 is down. Neither is a regression from this work,
  and neither is fixed by it.

### Mobile

The dashboard was overflowing its viewport on a phone. Root cause was `StatsBar`: a ~90px tile
cannot hold a 6-figure count at `text-2xl`, so the numbers spilled out of their cards. Fixed there
plus `AISearch` (placeholder clipping), the leaderboard table (5 columns crushed into 4-line
stacks — phone now shows airline + on-time % + cancelled %, the rest return at `sm`), and page
rhythm. Page-level horizontal overflow is 0px at 320px and 1440px on every page.

Separately, `index.css` carried an `[dir="rtl"] .grid-cols-2 > :first-child { order: 2 }` rule that
reordered on top of CSS Grid's own RTL flow and scrambled **any** 2-column grid holding more than
two items — the recovery buckets rendered never/expanded/recovered/partial, and the flight-board
filters and admin KPI tiles were shuffled the same way. `StatsBar` had already been rewritten to
dodge it. The rule is removed, with a comment where it was.

## Goal

RankAir today is a single answer-machine: *"which airline should I take to city X?"*. This plan adds
three pages that use the same 157k-row dataset to answer three different questions, plus the tab bar
that ties them together.

| Route | Hebrew | Question it answers |
|---|---|---|
| `/` (existing) | דירוגים | Which airline to a given destination? |
| `/airlines` | ביצועי חברות | How good is this airline, really? |
| `/insights` | תובנות | What does the data reveal that nobody looks for? |
| `/recovery` | מי חזר לטוס | Which carriers came back after the crisis — and who never did? |
| `/flight-board` (existing) | לוח טיסות | What is happening right now? |

Charts: Recharts, via the existing `frontend/src/components/ui/chart.tsx` shadcn wrapper. No new
dependencies. Light/dark aware, RTL aware.

---

## Evidence base

Everything below was measured against the production DB through the read-only role
(`DATABASE_URL_RO`) on 2026-07-24. Data window: **2025-09-05 → 2026-07-27** (future rows are
scheduled flights), 157,036 rows, 78,778 departures.

**Cancellation and volume, departures, by carrier nationality**
(Israeli = `LY`, `IZ`, `6H`, `ER`, `E2`):

| Month | Foreign scheduled | Foreign cancelled | Israeli scheduled | Israeli cancelled |
|---|---|---|---|---|
| 2026-01 | 5,436 | 2.7% | 3,019 | 2.0% |
| 2026-02 | 4,891 | 3.3% | 2,638 | 2.4% |
| **2026-03** | 1,284 | **80.8%** | 1,862 | **39.6%** |
| **2026-04** | **318** | 11.6% | 1,954 | 7.6% |
| 2026-05 | 2,016 | 1.2% | 3,466 | 1.3% |
| 2026-06 | 4,330 | 2.0% | 4,367 | 1.1% |
| 2026-07 | 5,006 | 0.9% | 4,407 | 2.2% |

Two distinct behaviours, which is the actual story:
- **March** — foreign carriers cancelled 4 of every 5 flights already on the board (80.8%).
  Israeli carriers cancelled 2 of 5 (39.6%).
- **April** — foreign carriers stopped *scheduling* at all: 318 flights against 4,891 in February
  (−94%). Israeli carriers went the other way and **grew** their April schedule (1,954 vs 1,862
  in March).

**Distinct carriers operating ≥1 non-cancelled departure per month:**
72 (Feb) → 55 (Mar) → **26** (Apr) → 53 (May) → 54 (Jun) → 62 (Jul). Still below pre-crisis.

**Punctuality patterns** (departures, non-cancelled, on-time = `delay_minutes <= 15`):
- By weekday: Saturday **56.2%** on-time vs Thursday **30.4%**. Every other day 32–38%.
- By hour: best around 12:00 (44.2%), worst at 16:00–17:00 (~28%). Average delay climbs from
  ~25 min at dawn to ~39 min by 18:00.

**Market share shift**: Israeli carriers were 35% of departures in February, 47% in July.

---

## Page 1 — Nav bar

Sticky tab bar directly under the existing header row in each page's layout.

```
┌──────────────────────────────────────────────────────┐
│ 🛫 RankAir                         [EN/עב] [☀/🌙]    │
├──────────────────────────────────────────────────────┤
│  דירוגים · ביצועי חברות · תובנות · מי חזר · לוח טיסות │  ← sticky
└──────────────────────────────────────────────────────┘
```

- New `SiteNav.tsx` + a shared `PageLayout.tsx` wrapping header + nav + footer, so the credits
  block and header stop being duplicated per page.
- The `DatabaseToggle` "flight board" button leaves the header and becomes a tab. That also
  removes the mobile-only duplicate block in `Index.tsx:99-105`.
- Underline active-tab style; horizontal scroll on mobile; `aria-current="page"` on the active tab.
- `/admin` stays unlisted.

**Decision — routing**: keep the existing flat `react-router` `Routes` in `App.tsx` and have each
page render `<PageLayout>`, rather than converting to nested layout routes. Smaller diff, no change
to how the existing three pages mount.

**Deployment note**: new deep links (`/airlines`, `/insights`, `/recovery`) rely on
`frontend/vercel.json` already rewriting `/(.*)` → `/index.html`. It exists; no change needed.

---

## Page 2 — `/airlines` (ביצועי חברות)

**Revised 2026-07-25 after review.** The original proposal here was a leaderboard plus a
reliability scatter — a ranking page. That was the wrong premise and was rejected. The page is
**one airline under a microscope**: its total performance, and its performance on every route it
flies. It is the mirror of the front page — home is destination-first ("pick Paris, compare
airlines"), this is airline-first ("pick El Al, compare its destinations").

**Entry** — an airline search box at the top, mirroring `DestinationSearch` on home. Selecting a
carrier deep-links to `/airlines/:code`, so a specific airline is shareable.

**Sections, top to bottom**

1. **Identity + KPI tiles** — flights, on-time %, cancelled %, avg delay when late, destinations
   served. Each tile carries a quiet "vs airport average" line, because a bare 41.2% tells the
   reader nothing without knowing TLV runs 36.5%. Context only — no rank, no league table.
2. **Delay profile** — one stacked bar: early / 0–15 / 15–60 / 60+ / cancelled. Across TLV the
   split is 1.6% / 34.9% / 51.8% / 11.7%, so *how* late a carrier runs is the real
   differentiator and a single on-time percentage hides it.
3. **Monthly on-time trend** — 11 months, so the carrier's own disruption dip and recovery show.
4. **Per-destination table — the centrepiece.** Every route: flights, on-time %, cancelled %,
   avg delay. Sortable and searchable, with best/worst route called out above it.

Why the per-route table carries the page: El Al overall is ~41% on time, but that is
**61.4% to Abu Dhabi and 12.9% to Chisinau** (22.4% to Amsterdam, 24.7% to Frankfurt). The
headline number conceals a 48-point spread inside a single airline.

Route counts under the canonical grouping: Arkia 98, El Al 84, Israir 81; foreign carriers 1–24,
so the table is short for most of them but never empty.

### Existing endpoint must be rewritten, not reused

`GET /api/v1/airlines/{code}/destinations` already exists and looks like it does this job. It
cannot be used as-is — three defects, all producing quietly wrong numbers that would disagree with
the front page for the same route:

- **On-time is `delay_minutes BETWEEN 0 AND 20`** — 20 minutes where the rest of the site uses 15,
  and the lower bound excludes early departures, so a flight leaving 5 minutes early is counted as
  *not* on time.
- **Cancellations use `status_en == 'CANCELED'`** directly instead of `flight_status.py`. That
  module exists because this exact drift happened before; this call site is the drift, still live.
- **Destination granularity flips with language** — Hebrew groups by `country_he`, English by
  `location_city_en`, so the same airline reports a different number of destinations depending on
  the UI language.

The rewrite uses `CANCELLED_SQL` / `NOT_CANCELLED_SQL` and the canonical destination grouping
already used by `/destinations/cities` (group by the first Hebrew word of `location_he`, falling
back to `location_city_en`; English name is `MIN(location_city_en)`), so London Luton and Stansted
collapse into one LONDON / לונדון row exactly as they do elsewhere on the site.

Delivered as new endpoints rather than an in-place edit, so nothing depending on the old handler
breaks: `GET /airlines/directory`, `GET /airlines/{code}/profile`, `GET /airlines/{code}/routes`.
The defective `/{code}/destinations` is left in place but marked `@deprecated` in
`frontend/src/config/api.ts`; nothing in the frontend was calling it.

**Label fix on top of the canonical grouping.** The group *key* is the first Hebrew word, which is
right for grouping but wrong as a display label — it renders 'אבו דאבי' as 'אבו'. The routes
endpoint therefore labels each group with the **shortest full** Hebrew name in it, which still
collapses London's airports to a bare 'לונדון' but keeps multi-word cities intact.

### Three sample-size guards, each added after seeing the page get it wrong

Every one of these was a plausible-looking number the data could not support:

| Where | What it claimed | Guard |
|---|---|---|
| Best-route callout | Bacau as El Al's best route at 75% — off **12 flights, a third of them cancelled** — ahead of Abu Dhabi's 63.5% across 1,143 | Callouts drawn only from routes with ≥50 flights, hidden entirely if fewer than 2 qualify; sample size printed beside the claim |
| Monthly trend | Delta at **100% on-time in March 2026**, the month it almost stopped flying — 71 scheduled, only 12 operated | Months with <30 measured flights plot as `null`, leaving an honest gap in the line rather than a spike |
| Route table | A 2-flight route at 100% | Routes below 10 flights excluded; flight count shown on every row so thin rows can be judged |
| Worst-delay KPI | Arkia "2,883 min" reading as a property of the airline | The tile names the flight it came from (`1169 · לרנקה · 4 באפר׳`) |

**Superseded 2026-07-25 — the definition was fixed instead of the label.** Naming the flight was
treating the symptom. A flight that departs two days late was not delayed; it was cancelled and its
passengers rebooked, and the upstream feed simply never changed the status from `DEPARTED`. That
rule now lives in `flight_status.py` as `MAX_PLAUSIBLE_DELAY_MIN`, so it applies everywhere on the
site at once rather than being patched per page.

Threshold set to **1440 minutes (24 hours)**. The originally specified 25 hours left El Al's worst
delay at 1,499 minutes — 24.98 hours, one minute under the line — which reads exactly like the
problem it was meant to remove. A full calendar day is also the cleaner concept: past it, the next
day's equivalent service has already gone.

Blast radius is tiny and the affected rows are unambiguous: **16 of 151,527 (0.01%)**, being 48h,
41.5h, three IDENTICAL 36.4h Athens arrivals across three different carriers (a feed artifact, not
three real delays), 30.4h, 25.4h, 25.0h, 24.2h and similar. Effects:

| | Before | After |
|---|---|---|
| Arkia worst delay | 2,883 min (48.0h) | 1,170 min (19.5h) |
| El Al worst delay | 1,499 min (25.0h) | 1,206 min (20.1h) |
| Highest surviving departure delay, site-wide | 2,883 min | 1,206 min |
| March 2026 foreign cancellation rate | 80.84% | 80.84% |
| Derived crisis window | 2026-03 → 2026-04 | unchanged |

`COALESCE(delay_minutes, 0)` in the fragment is load-bearing: `delay_minutes` is NULL for flights
with no recorded actual time, and without the guard `status OR NULL` is NULL, `NOT NULL` is NULL
too, and those rows would vanish from **both** the cancelled and not-cancelled sets — silently
dropping out of every aggregate on the site. `tests/test_flight_status.py` pins this, along with
the boundary behaviour and the SQL/ORM equivalence. 12 tests, and they actually run (the ORM
predicate works on SQLite).

**Original finding, retained for context.** The figure was arithmetically correct — Arkia IZ 1169 to
Larnaca, scheduled 2026-04-04 19:00, departed 2026-04-06 19:03, exactly 2 days and 3 minutes. The
stored `delay_minutes` column was audited against `actual_time - scheduled_time` across all 75,866
operated departures and disagrees on **zero** rows, so there is no rollover bug anywhere in the ETL.

The problem was interpretive, not arithmetic. `MAX` is a one-observation statistic: Arkia's median
delay is 30 min, p90 94 min, p99 288 min — the max is **ten times its own 99th percentile**, set by
1 flight out of 5,966 delayed ones. Worse, 2026-04-04 falls inside the disruption window, so that
flight is really a two-day postponement the feed recorded as `DEPARTED` rather than `CANCELED`.
Only 4 departures airport-wide exceed 24 hours and two of them sit in the crisis months, meaning
the bare tile was partly measuring the disruption rather than the carrier.

Naming the flight keeps the striking number while making it a checkable fact about one departure.
The alternative — swapping to p99 — was considered and not taken: it is more robust but loses the
concrete detail, and the tile is not a metric anyone ranks carriers by.

The trend guard needed a new `measured` field in the profile response — the count the percentage is
actually computed from, which is not the scheduled count whenever a carrier has cancellations.

### Design decisions

- **Compare the airline to itself, never to other airlines.** An airport-wide benchmark was built
  and then removed on review: each route is measured against *that airline's own* overall on-time
  share (`vs its own average`), and the trend chart's reference line is the airline's own average.
  A cross-carrier figure would quietly turn the page back into a ranking.
- Entry is a search box deep-linking to `/airlines/:code`, mirroring `DestinationSearch`.

Verified on production data: El Al 20,156 departures, 37.2% on time, 84 destinations, best route
Abu Dhabi +26.3 points against its own average, worst Chisinau −23.9 — a 50-point spread inside one
airline that the headline number completely hides.

---

## Page 3 — `/insights` (תובנות)

Vertical scroll of **story cards**: headline + chart + one short paragraph. Every number fetched
live from the API — nothing hardcoded, so the page stays true as the ETL runs.

1. **"כשהשמיים נסגרו" / When the sky closed** — stacked monthly departures (Israeli vs foreign)
   with a cancellation-rate line overlay, March–April shaded.
2. **"שבת היא היום הכי טוב לטוס"** — weekday bar chart. Saturday 56.2% vs Thursday 30.4%.
3. **"הקיר של ארבע אחר הצהריים"** — hourly line chart. On-time collapses to ~28% at 16:00–17:00.
4. **"יתרון כחול-לבן"** — Israeli carrier share of departures, 35% → 47%.

Each card carries a plain-language caption stating the metric definition, so the numbers are not
presented without their basis.

---

## Page 4 — `/recovery` (מי חזר לטוס)

A live tracker, not a historical story — it re-computes on every ETL cycle, so a carrier resuming
next month shows up without a code change.

Measured model (validated 2026-07-24, 62 carriers with ≥60 baseline flights):

- **baseline** = average monthly operated departures, 2025-09-01 → 2026-03-01 (6 months)
- **last 30 days** = operated departures in the trailing 30 days
- **recovery %** = last 30 days ÷ baseline

Four buckets fall out naturally:

| Bucket | Count | Examples (recovery %) |
|---|---|---|
| 🔴 Never came back | 9 | JetBlue, United, Brussels, Transavia France, ANA, Swiss, British Airways, Iberia Express, FlyYo |
| 🟠 Partially back | ~12 | Hainan 5%, FlyOne Romania 19%, Eurowings 23%, Air Canada 36%, Virgin Atlantic 54%, Wizz Air Malta 57%, Lufthansa 67% |
| 🟢 Fully recovered | ~25 | flydubai 105%, Delta 108%, SAS 111%, Emirates 127%, Air France 128%, Etihad 137% |
| 🔵 Expanded into the gap | ~15 | Arkia 180%, Israir 169%, El Al 138%, TUS 253%, Blue Bird 381%, Air Serbia 486% |

That fourth bucket is a finding in its own right: some carriers did not merely recover, they grew
into the vacuum left by the ones that never returned.

**Layout**
- Four summary tiles, one per bucket, with counts.
- **Return timeline** — horizontal Gantt of resumption dates, earliest first: TUS Apr 14 →
  Etihad Apr 15 → flydubai Apr 16 → Emirates May 4 → Delta May 17 → Wizz May 28 → Lufthansa Jul 1.
  Carriers that never returned sit in a greyed "still missing" band at the bottom.
- **Table** — carrier, baseline/month, return date, last-30-days, recovery %, bucket. Sortable,
  filterable by bucket.

**Two definition traps found while validating — must be handled in the endpoint:**

1. *A single flight is not a return.* Georgian Airways has a first-flight-back date of 2026-04-17
   but **zero** flights in the last 30 days. Bucketing must be driven by trailing-30-day volume,
   with the first-flight date shown only as supporting detail.
2. *Carriers that never stopped must not be shown as "returning".* El Al, Arkia and Israir report a
   return date only because the query window opened on 2026-04-05. The endpoint must require a
   genuine gap (≥14 consecutive days with no operated departure) before assigning a return date.

---

## Backend work

New router `backend/app/api/insights.py` (`/api/v1/insights`), all read-only aggregates:

| Endpoint | Feeds |
|---|---|
| `GET /monthly-by-nationality` | Insights story 1, story 4 |
| `GET /by-weekday` | Insights story 2 |
| `GET /by-hour` | Insights story 3 |
| `GET /carrier-recovery` | `/recovery` page (all four buckets + timeline + table) |

Extensions to `backend/app/api/airline_endpoints.py`:

| Endpoint | Feeds |
|---|---|
| `GET /airlines/{code}/trend` | Monthly on-time trend |
| `GET /airlines/{code}/delay-distribution` | Stacked delay histogram |

`GET /airlines/stats` already supports date range, `min_flights`, sorting and limit — it covers the
leaderboard and the reliability map without modification.

**New shared constant.** Israeli carrier classification (`LY`, `IZ`, `6H`, `ER`, `E2` — Air Haifa is
Israeli and is easy to miss) goes in a new `backend/app/services/carrier_nationality.py`, next to
`flight_status.py` and for the same reason that module exists: defined once, so the definition
cannot drift between call sites. Exports both a raw-SQL fragment and a SQLAlchemy predicate, mirroring
the `CANCELLED_SQL` / `is_cancelled()` pair.

Every new query reuses `CANCELLED_SQL` / `NOT_CANCELLED_SQL` from `flight_status.py`. No new
cancellation logic is written anywhere.

---

## Test plan

Written before the implementation, following the standing test-plan-first rule. New file
`backend/tests/test_insights_endpoints.py`, alongside the existing
`test_airline_endpoints.py` / `test_destination_endpoints.py`, using the same `conftest.py` fixtures.

**Carrier nationality** (`test_carrier_nationality.py`)
- `LY`, `IZ`, `6H`, `ER`, `E2` classify as Israeli; `LH`, `BA`, `EK` do not.
- The SQL fragment and the ORM predicate return the same set over a seeded fixture — the same
  equivalence guarantee `flight_status.py` carries.

**`/insights/monthly-by-nationality`**
- Months with zero flights for a nationality return a row with `0`, not a missing key (the chart
  must not silently drop April's foreign bar).
- Cancelled flights count toward `scheduled` but not toward `operated`.
- Percentages are computed against that month's own scheduled count, not the grand total.

**`/insights/by-weekday`, `/insights/by-hour`**
- Cancelled flights are excluded — a cancellation is not a punctuality data point.
- All 7 weekdays / 24 hours present even when a bucket is empty.
- Weekday indices follow Postgres `DOW` (0 = Sunday), matched by a fixture with a known date.

**`/insights/carrier-recovery`** — the two traps above are the priority cases:
- A carrier with a return date but zero trailing-30-day flights buckets as **never came back**,
  not "returned" (the Georgian Airways case).
- A carrier that operated continuously through March–April gets **no** return date and is excluded
  from the timeline (the El Al / Arkia / Israir case).
- A gap shorter than 14 days does not count as a stoppage.
- Carriers below the baseline threshold (<60 flights) are excluded, so a carrier with 2 lifetime
  flights cannot appear as "486% recovered".
- Division-by-zero guard: baseline of 0 must not 500.

**`/airlines/{code}/trend`, `/delay-distribution`**
- Distribution buckets sum to the carrier's total flight count — no row is dropped or double-counted
  at a boundary (a flight of exactly 15 min belongs to `0–15`).
- Unknown airline code returns an empty result, not a 500.

**Frontend** — no test runner is configured in `frontend/` today; this plan does not add one.
Verification is manual against `/docs` and the running dev server, and is listed as an explicit gap
rather than an implied pass.

---

## Suggested build order

1. `PageLayout` + `SiteNav`, retrofitted onto the three existing pages. Ships visible value with no
   backend change and de-duplicates the header/footer.
2. `carrier_nationality.py` + its tests + `/insights/*` endpoints.
3. `/insights` page (4 story cards).
4. `/insights/carrier-recovery` endpoint + tests, then the `/recovery` page.
5. `/airlines` leaderboard + reliability map.
6. `/airlines/:code` detail view.

Steps 1–4 are the LinkedIn-facing payload. Steps 5–6 are the depth a returning visitor uses.

## Open questions

- Should `/recovery` and `/insights` be separate tabs, or `/recovery` as a sub-tab of `/insights`?
  Written here as separate — the recovery tracker is live-updating and the insights stories are
  largely historical, which argues for separate.
- The crisis window is currently hardcoded as March–April 2026 for the shaded chart region. Worth
  deriving it from the data (months where the cancellation rate exceeds some threshold) so the page
  does not need editing if another disruption occurs.
