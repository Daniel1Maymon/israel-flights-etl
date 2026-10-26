# Rank Air — Israel Flights ETL

Compares how airlines perform at Ben Gurion airport.

Every 15 minutes it pulls the official flight board from `data.gov.il`,
stores it in PostgreSQL, and serves it through a FastAPI backend to a React
site. The site answers questions like *"which airline should I fly to Paris?"*,
in Hebrew or English, with an AI search that never touches the database
directly.

## The whole system in one picture

```
  data.gov.il (CKAN API)
  the official Ben Gurion flight board
        │
        │  HTTP, paged 1000 rows at a time
        ▼
 ┌───────────────────────────────┐
 │ ETL service          etl/     │
 │ APScheduler, every 15 min     │
 │                               │
 │ 1. fetch      etl/fetch.py    │
 │ 2. transform  etl/transform.py│
 │ 3. upsert     etl/load.py     │
 └───────────────┬───────────────┘
                 │  INSERT ... ON CONFLICT (flight_id) DO UPDATE
                 ▼
 ┌───────────────────────────────┐
 │ PostgreSQL                    │
 │  flights        (the data)    │
 │  ai_usage, ai_budget,         │
 │  ai_events, flags (AI search) │
 └───────┬───────────────┬───────┘
         │ app role      │ rankair_ro role
         │ (normal API)  │ (SELECT on flights only,
         │               │  2 s timeout, AI search)
         ▼               ▼
 ┌───────────────────────────────┐
 │ FastAPI backend   backend/    │
 │ gunicorn, 4 uvicorn workers   │
 │ airlines · destinations ·     │
 │ insights · flight board (SSE) │
 │ · AI search · admin           │
 └───────────────┬───────────────┘
                 │  JSON over HTTP, SSE for the live board
                 ▼
 ┌───────────────────────────────┐
 │ React site        frontend/   │
 │ Vite + TypeScript + shadcn/ui │
 └───────────────────────────────┘

  Hosting: Postgres, backend and ETL on Railway. Frontend on Vercel.
```

## One flight, from the API to the screen

How one row moves through the system:

```
 1. CKAN record (raw)      CHOPER, CHFLTN, CHSTOL, CHPTOL, CHAORD, CHLOC1, CHRMINE ...
                           (Hebrew-system column codes)
        │
 2. transform              CHOPER  → airline_code
                           CHFLTN  → flight_number
                           CHSTOL  → scheduled_departure  (parsed to datetime)
                           CHPTOL  → actual_departure     (parsed to datetime)
                           CHAORD  → arrival_departure_code (A / D)
                           CHRMINE → status_english
                           delay_minutes = actual − scheduled
        │
 3. flight_id              md5(airline_code + flight_number + A/D
                               + airport_code + scheduled_departure)
        │
 4. upsert                 same flight_id seen again → row is updated, not duplicated
                           (status and actual time change as the flight happens)
        │
 5. API                    e.g. GET /api/v1/destinations/airline-performance?city=PARIS
                           groups that city's flights by airline: flights, on-time %, avg delay
        │
 6. site                   the destination search table on the home page
```

Full column list: [docs/reference/FIELD_MAPPING_TABLE.md](docs/reference/FIELD_MAPPING_TABLE.md).

## The parts

| Folder | What it is | Entry point |
|---|---|---|
| `etl/` | Small scheduler. Runs fetch → transform → upsert once at start, then every `SCHEDULE_INTERVAL_MINUTES` (15). | `python -m etl.main` |
| `backend/` | FastAPI API. Read-only queries over `flights`, plus the AI search. | `app/main.py` |
| `frontend/` | React site, 6 pages (below). | `src/App.tsx` |
| `airflow/` | Older Airflow version of the pipeline (S3, Mongo, Elasticsearch). Not part of the default runtime. | `airflow/dags/flight_pipeline.py` |

## Backend layers

```
gunicorn (4 workers)
   │ imports
   ▼
app/main.py           builds the app: CORS, request logging, global error handler.
   │                  On startup: checks the DB, creates the AI-search tables once
   │                  (under a Postgres advisory lock, so workers don't deadlock).
   ▼
app/api/router.py     the table of contents, one line per feature router
   ├── health.py            /  /health  /ready  /metrics
   ├── airline_endpoints.py /api/v1/airlines         stats, top-bottom, top-on-time
   ├── airline_profile.py   /api/v1/airlines         directory, {code}/profile, {code}/routes
   ├── destinations.py      /api/v1/destinations     city search, airline performance by city
   ├── stats.py             /api/v1/stats/overview   the numbers bar on the home page
   ├── insights.py          /api/v1/insights         by month, weekday, hour, carrier recovery
   ├── flight_board.py      /api/v1/flight-board     live board (SSE) + filter options
   ├── ai_search.py         /api/v1/ai-search        POST, the free-text question
   └── admin.py             /api/v1/admin            AI usage, events, LLM switch
   ▼
app/services/         the logic: SQL aggregations, flight status rules, AI pipeline
```

To add a feature: write one router file, add one line to `router.py`.

## The site

| Page | Route | What it shows | Backend |
|---|---|---|---|
| Home | `/` | Pick a destination, see airlines ranked for it. Ask the AI a question. | `destinations/*`, `stats/overview`, `ai-search` |
| Flight board | `/flight-board` | Live arrivals and departures, with filters | `flight-board/stream` (SSE), `flight-board/options` |
| Airlines | `/airlines`, `/airlines/:code` | All airlines, and one airline's profile and routes | `airlines/*` |
| Insights | `/insights` | Patterns by month, weekday, hour; Israeli vs foreign carriers | `insights/*` |
| Recovery | `/recovery` | Which foreign airlines came back after the crisis, and how much | `insights/carrier-recovery` |
| Admin | `/admin` | AI search usage, events and model choice | `admin/*` |

**Live flight board.** On connect, the server sends every flight in the current
window. Then it re-queries every 15 minutes (same as the ETL) and pushes a full
update. A heartbeat keeps proxies from closing the connection. The number of
open streams is capped; past the cap the server answers 503 instead of hanging.

## AI Search

Ask a plain-language question and get an answer computed from the live flight
data. One question, one answer (no chat memory). The LLM provider is set with
env vars (`LLM_PROVIDER`, `LLM_MODEL`); OpenRouter, OpenAI and Gemini are
supported.

```
 question
    │
    ▼
 guards ───────────────────────── over a limit ──► refuse
  monthly budget · per-user daily cap · length
    │
    ▼
 1. interpret   LLM → intent as JSON (not SQL)
    │           off-topic or injection ──────────► refuse
    ▼
 2a. common question  → reviewed SQL handler, bound parameters
 2b. anything else    → LLM writes SQL → AST validator → run
    │                     (one SELECT, allowed tables only, forced LIMIT)
    │
    │   both run as rankair_ro: SELECT on flights only, 2 s timeout
    │   zero rows ───────────────────────────────► refuse
    ▼
 3. format      LLM writes 3–4 lines from the rows only
    ▼
 answer + rows → the site
```

### One question, step by step (real example)

A real run, saved by the probe script in
[`backend/scripts/ai_probe_results/20260725-192312-en.jsonl`](backend/scripts/ai_probe_results/20260725-192312-en.jsonl)
(case `rank-02`). Each box shows what goes in and what comes out.
`[LLM]` marks a model call. Everything else is plain code.

```
 POST /api/v1/ai-search
 { "question": "which airline has the best on-time performance to London?" }
        │
        ▼
 ┌─ 0. guards ─────────────── api/ai_search.py ──────────────────────────┐
 │ length ok · this user's daily cap ok · monthly token budget ok        │
 └───────────────────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─ 1. interpret  [LLM] ───── llm_tasks.interpret() ─────────────────────┐
 │ system: "You classify and parse user questions for RankAir ...        │
 │          Return JSON matching the schema. NEVER write SQL."           │
 │ user:   the question as typed                                         │
 │ temperature 0, output forced to the Intent schema                     │
 │                                                                       │
 │ out: { "valid": true, "intent": "rank_airlines",                      │
 │        "destination": "London", "metric": "on_time", "limit": 10 }    │
 └───────────────────────────────────────────────────────────────────────┘
        │   valid = false (off-topic / only an injection) ──► refuse
        ▼
 ┌─ 2. resolve destination ── destination_resolver.resolve() ────────────┐
 │ "London" is in the city list built from the data → direct hit,        │
 │ 0 tokens. Only a name not in the list (Crete → HERAKLION) costs       │
 │ one small [LLM] call, and it may only pick a name from that list.     │
 │                                                                       │
 │ out: ("city", "LONDON")                                               │
 └───────────────────────────────────────────────────────────────────────┘
        │   not in the data ──► refuse ("no data"), never an unfiltered query
        ▼
 ┌─ 3. run the query ──────── ai_query_handlers.run_query_handler() ─────┐
 │ rank_airlines has a reviewed handler: fixed SQL, bound parameters,    │
 │ HAVING COUNT(*) >= 10, run as the read-only rankair_ro role.          │
 │                                                                       │
 │ out: 9 rows, e.g.                                                     │
 │   Airline                Total Flights  On-Time %  Avg Delay (min)    │
 │   BRITISH AIRWAYS PLC              132       47.0             21.6    │
 │   SAS                              289       42.2             25.7    │
 │   DELTA AIRLINES                   205       40.5             29.0    │
 │   EL AL ISRAEL AIRLINES            889       36.7             30.3    │
 │   ...                                                                 │
 │ Column names are relabeled here, so no raw DB column leaves the API.  │
 └───────────────────────────────────────────────────────────────────────┘
        │   0 rows ──► refuse ("no data")
        ▼
 ┌─ 4. format  [LLM] ──────── llm_tasks.format_answer() ─────────────────┐
 │ system: "You are RankAir ... write a concise 3-4 line answer ...      │
 │          Use ONLY the numbers in the rows; never invent figures."     │
 │ user:   Question + Rows (JSON) + "About these rows":                  │
 │         sorted by · showing N of M · truncated · min-sample rule      │
 │ temperature 0.2                                                       │
 └───────────────────────────────────────────────────────────────────────┘
        │
        ▼
 answer: "BRITISH AIRWAYS PLC had the best on-time performance to London,
          with 47.0% of its 132 flights arriving on time. The next best
          was SAS, with an on-time performance of 42.2% across 289
          flights. ISRAIR AIRLINES had the lowest on-time performance at
          16.1% for its 168 flights."
 + the 9 rows as a table

 This run: 2 LLM calls · 1,187 tokens · 2.6 s · source = "handler"
```

**When no handler fits**, step 3 changes. Real case `ops-01`,
*"which terminal is the busiest?"*:

```
 1. interpret  [LLM]  → { "valid": true, "intent": "other" }
 3. generate SQL [LLM] llm_tasks.generate_sql()
                       prompt holds the columns, today's date and the data window
                       → SELECT terminal, COUNT(*) AS total_flights FROM flights
                         WHERE scheduled_time <= '2026-07-25 00:00:00'
                         GROUP BY terminal ORDER BY total_flights DESC LIMIT 1
    sql_guard          parses the SQL: one SELECT, flights only, LIMIT forced
                       rejected ──► refuse ("unsupported")
    run_readonly       rankair_ro role, 2 s timeout → 1 row: Terminal 3, 147,708
 4. format     [LLM]  → "Terminal 3 is the busiest, with 147,708 total flights."

 This run: 3 LLM calls · 1,304 tokens · 2.3 s · source = "fallback"
```

Two safety walls sit under the LLM, and each works on its own:

- **Postgres itself.** The `rankair_ro` role can only `SELECT` from `flights`.
  Writes, drops and other tables are denied by the database.
- **The AST validator** (`services/sql_guard.py`) for LLM-written SQL. It parses
  the SQL, it doesn't regex it.

Every refusal shows one of two fixed sentences, in the question's language.
Every question and its outcome is logged to `ai_events` for the admin page.

Full details: [docs/AI_SEARCH.md](docs/AI_SEARCH.md).

## Quick Start

Prerequisites:
- Docker + Docker Compose
- Python 3.11+ (local development)
- Node.js 20+ (frontend development)

### Option A: Full local stack (with local PostgreSQL)

Use the production compose file (it includes Postgres):

```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose-prod.yml --env-file .env.prod up -d --build
```

Access:
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs` (only when `ENABLE_API_DOCS` is set)

### Option B: Railway-style services locally

`docker-compose.yml` matches the Railway setup. It expects an external managed
database via `DATABASE_URL` (the Postgres service is commented out there).

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Environment variable:
- `VITE_API_URL` (defaults to `http://localhost:8000`)

### ETL

```bash
cd etl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m etl.main
```

## Testing

Backend tests:

```bash
cd backend
pytest
```

More details:
- `backend/tests/README.md`
- `backend/tests/HOW_TESTING_WORKS.md`

Frontend quality checks:

```bash
cd frontend
npm run lint
npm run build
```

## Deployment

- Railway + Vercel quick path: [QUICK_DEPLOY.md](QUICK_DEPLOY.md)
- EC2 + Docker Compose path: [DEPLOYMENT.md](DEPLOYMENT.md)

## Docs

Start here:
- [docs/INDEX.md](docs/INDEX.md)
- [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)
- [docs/AI_SEARCH.md](docs/AI_SEARCH.md) — AI Search architecture and how it works
- [docs/planning/RANKAIR_DESIGN.md](docs/planning/RANKAIR_DESIGN.md) — how airlines are compared per destination

## License

[docs/legal/LICENSE](docs/legal/LICENSE)
