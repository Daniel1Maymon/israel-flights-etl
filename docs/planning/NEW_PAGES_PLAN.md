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
| 6. `/airlines` leaderboard + reliability map | **not started** |
| 7. `/airlines/:code` detail view | **not started** |

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

Home answers "which airline to Paris". This answers "how good is this airline".

**Filter bar** — date range (3 / 6 / 12 months · since the crisis · all time), min flights,
departures/arrivals, country.

**Podium** — top 3 cards, medal, on-time %, flight count.

**Leaderboard** — all ~104 airlines, sortable on every column, rank badge. Reuses
`DestinationPerformanceTable`, which already does client-side multi-column sort.

**Reliability map** — scatter chart: x = on-time %, y = avg delay, bubble size = flight volume,
colour = Israeli/foreign. Separates "big and reliable" from "punctual but tiny sample", which the
`min_flights` filter alone cannot show.

**Detail view `/airlines/:code`**
- KPI tiles: flights · on-time % · cancelled % · avg delay · worst delay
- Monthly on-time trend across the 11-month window (each carrier's crisis dip is visible here)
- Delay distribution, stacked bar: early / 0–15 / 15–60 / 60+ / cancelled
- Top destinations with per-route on-time %
- Best and worst hour to fly this carrier

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
