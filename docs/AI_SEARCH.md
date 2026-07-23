# AI Search — Architecture & How It Works

RankAir's AI Search lets a user ask a free-text question (Hebrew or English) — e.g.
*"which airline should I fly to Paris and why?"* — and get a grounded answer computed from the
live `flights` database. It is **single-shot** (no chat memory), **cheap** (a small LLM does the
language work), and **security-first** (the LLM can never touch the database directly).

This doc gives the macro picture first, then the feature.

---

## 1. How the backend is structured

The backend is a FastAPI app. In production it is started by one command:

```
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

That means: **import the `app` object from `app/main.py` and run 4 worker copies of it.**

Routing is organized in three layers — endpoints are *not* defined in `main.py`:

```
gunicorn (4 workers)                    ← the running server process
   │ imports
   ▼
app/main.py  →  app = FastAPI()         ← assembles the app + middleware; defines NO endpoints
   │  middleware: CORS · request logging · global error handler
   │  app.include_router(api_router)
   ▼
app/api/router.py  →  api_router        ← "table of contents": includes every feature router
   ├── health.py            (no prefix) ....  /  /health  /ready  /metrics
   ├── flights.py           /api/v1/flights
   ├── airline_endpoints.py /api/v1/airlines
   ├── destinations.py      /api/v1 .........  powers the city search box
   ├── flight_board.py      /api/v1/flight-board
   └── ai_search.py         /api/v1/ai-search .. the natural-language question
```

Each feature file owns an `APIRouter(prefix=...)` and its handler functions. **To add a feature:
write one file, add one line to `router.py`.**

### Endpoint map

| Router file | URL prefix | Serves |
|---|---|---|
| `health.py` | *(none)* | health / readiness / metrics |
| `flights.py` | `/api/v1/flights` | raw flight lists, airline list |
| `airline_endpoints.py` | `/api/v1/airlines` | airline stats, top/bottom |
| `destinations.py` | `/api/v1` | `destinations/cities`, `destinations/airline-performance` (the city search) |
| `flight_board.py` | `/api/v1/flight-board` | live SSE board, filter options |
| `ai_search.py` | `/api/v1/ai-search` | **POST — the AI question** |

### What happens when a request arrives

1. Browser → a gunicorn/uvicorn worker (the running `app`).
2. Middleware runs (CORS check, request logged).
3. FastAPI matches the request's **method + path** to exactly one handler.
4. It calls that handler (resolving its dependencies, e.g. a DB session).
5. The handler returns a Python object → serialized to JSON.
6. Any unhandled error → the global exception handler returns a clean JSON error.

So a city typed into the search box → `GET /api/v1/destinations/airline-performance`; a free-text
AI question → `POST /api/v1/ai-search`. Same app, different routes.

---

## 2. The AI Search feature

Two roles, in two same-named files (different layers):

| | File | Function | Role |
|---|---|---|---|
| **Entry point** | `app/api/ai_search.py` | `ai_search()` | HTTP door: runs the guards, then delegates |
| **Orchestrator** | `app/services/ai_search.py` | `answer_question()` | conducts the pipeline (no HTTP concerns) |

### The flow (one question, end to end)

```
question
  │  api/ai_search.py — guards: monthly budget · per-user daily cap · length   (over any → refuse)
  ▼
answer_question()  (services/ai_search.py)
  │  1. INTERPRET   llm_tasks.py → provider   →  Intent JSON (not SQL)
  │                 off-domain / injection → valid:false → refuse
  │  2a. HANDLER    ai_query_handlers.py      →  reviewed, parameter-bound SQL   (common questions)
  │  2b. FALLBACK   llm_tasks.py writes SQL → sql_guard.py validates (AST) → run  (anything else)
  │       both run on ai_db.py — the READ-ONLY role (SELECT-only, 2s timeout, LIMIT)
  │  3. FORMAT      llm_tasks.py → provider   →  3–4 line answer built only from the rows
  ▼
answer + rows  →  rendered by AISearch.tsx (frontend)
```

### Components

| File | Job |
|---|---|
| `frontend/.../AISearch.tsx` | the search box; sends the question, renders the answer + table |
| `api/ai_search.py` | entry point — cost/abuse guards, identity cookie, token accounting |
| `services/ai_search.py` | orchestrator — interpret → handler/fallback → format |
| `services/llm_tasks.py` | the three LLM steps (interpret, generate SQL, format); prompts live here |
| `services/llm/` | **provider-agnostic** LLM layer (`base` interface + `gemini`, `openai` impls) |
| `services/ai_query_handlers.py` | reviewed SQL query handlers for common question shapes |
| `services/sql_guard.py` | AST validator for the fallback's LLM-written SQL |
| `services/ai_db.py` | the read-only DB connection all AI queries run through |
| `services/ratelimit.py` | per-user daily cap + monthly budget kill-switch (Postgres counters) |
| `schemas/ai_search.py` | request / response + the `Intent` structured-output contract |

### Why it's safe

Two independent walls sit under the LLM, so even a fully-jailbroken model does no harm:

1. **Read-only DB role** (`rankair_ro`) — `SELECT` on `flights` only, 2-second statement timeout.
   Writes, drops, and reads of any other table are denied by Postgres itself.
2. **Parser-based SQL guard** — the fallback's LLM SQL is validated as an AST (single `SELECT`,
   no writes, whitelisted tables only, forced `LIMIT`) — not fragile regex.

Common questions never involve LLM-written SQL at all: they run **reviewed query handlers** with
values passed as bound parameters, so answers are correct and injection is structurally impossible.

### Provider-agnostic LLM

Nothing outside `services/llm/` imports a vendor SDK. Switch provider or model with env vars —
no code change; adding a provider is a single new file implementing one method.

```
LLM_PROVIDER=gemini        # or openai
LLM_MODEL=gemini-2.5-flash
```

### Configuration (defaults)

| Setting | Env var | Default |
|---|---|---|
| Provider / model | `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / `gemini-2.5-flash` |
| API key | `GEMINI_API_KEY` (or `OPENAI_API_KEY`) | — (required) |
| Read-only DB URL | `DATABASE_URL_RO` | — (the `rankair_ro` role) |
| Per-user daily cap | `AI_DAILY_LIMIT_PER_USER` | `20` |
| Monthly token budget | `AI_MONTHLY_BUDGET_TOKENS` | `20000000` |
| Max question length | `AI_MAX_QUESTION_CHARS` | `500` |
| Forced row limit | `AI_MAX_ROWS` | `50` |

---

## TL;DR

`gunicorn` runs `main.py`'s `app`; `app` pulls in every router via `router.py`; each router
defines endpoints; a request is matched by its URL to one handler. A question POSTed to
`/api/v1/ai-search` hits `ai_search()` (guards) which calls `answer_question()` (the orchestrator),
which interprets the question, runs a reviewed query handler (or a guarded SQL fallback) on a
read-only database connection, and formats the rows into a plain-language answer.
