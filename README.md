# Israel Flights ETL System

End-to-end pipeline for Israeli flight data:
- Fetches from `data.gov.il` CKAN API
- Transforms + upserts into PostgreSQL
- Serves data via FastAPI
- Visualizes in a React dashboard

## Current Architecture

Data flow:

`CKAN API -> ETL (APScheduler, every 15 min) -> PostgreSQL -> FastAPI -> React`

Main components:
- `etl/`: Lightweight scheduler + ETL logic (`python -m etl.main`)
- `backend/`: FastAPI API (`/docs`, `/health`, `/ready`)
- `frontend/`: Vite + React dashboard
- `airflow/`: Legacy/alternate orchestration assets (not required for the current default runtime)

## AI Search

Ask a plain-language question — *"which airline should I fly to Paris and why?"* — and get an
answer computed from the live flight data (Hebrew or English). Single-shot, provider-agnostic LLM,
and security-first: the model never touches the database directly.

Flow: `question → guards (monthly budget · per-user daily cap) → interpret (LLM → structured intent)
→ reviewed query handler, or a guarded LLM-written SQL fallback → read-only DB → format → answer`.

Two independent safety walls sit under the LLM:
- a **read-only DB role** (`SELECT` on `flights` only, 2s timeout) — writes, drops, and other
  tables are denied by Postgres itself;
- an **AST SQL validator** for the fallback (single `SELECT`, whitelisted tables, forced `LIMIT`) —
  not fragile regex.

Common questions never use LLM-written SQL — they run reviewed query handlers with bound
parameters, so answers are correct and injection is impossible. Switch model/provider with env
vars (`LLM_PROVIDER`, `LLM_MODEL`) — no code change.

Endpoint: `POST /api/v1/ai-search`. Full details: [docs/AI_SEARCH.md](docs/AI_SEARCH.md).

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
- API docs: `http://localhost:8000/docs`

### Option B: Railway-style services locally

`docker-compose.yml` is aligned for Railway-like setup and expects an external managed database via `DATABASE_URL` (Postgres service is intentionally commented out there).

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

## API Surface (High Level)

- `GET /health`, `GET /ready`, `GET /metrics`
- `GET /api/v1/flights/*` (list/filter/pagination)
- `GET /api/v1/airlines/*` (aggregations, top/bottom, destinations)
- `GET /api/v1/destinations/*` (search, city autocomplete, airline performance by city)
- `GET /api/v1/flight-board/stream` (SSE live board)
- `GET /api/v1/flight-board/options` (flight-board filter values)
- `POST /api/v1/ai-search` (natural-language question → grounded answer; see [docs/AI_SEARCH.md](docs/AI_SEARCH.md))

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
- [docs/guides/PROJECT_GUIDE.md](docs/guides/PROJECT_GUIDE.md)
- [docs/AI_SEARCH.md](docs/AI_SEARCH.md) — AI Search architecture & how it works

## License

[docs/legal/LICENSE](docs/legal/LICENSE)
