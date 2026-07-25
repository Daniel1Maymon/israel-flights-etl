# Israel Flights ETL - Backend System Design

## 1. Purpose
This document describes the current backend-side architecture for the Israel Flights ETL project, including data ingestion, storage, API serving, and operational behavior.

## 2. Current Architecture (Source of Truth)

### Runtime data path
`data.gov.il CKAN API -> ETL scheduler (APScheduler) -> PostgreSQL -> FastAPI -> Frontend clients`

### Main backend components
- `etl/main.py`: scheduler entrypoint; runs one immediate ETL cycle on startup, then repeats on an interval.
- `etl/fetch.py`: paginated CKAN fetch (`limit`/`offset`).
- `etl/transform.py`: schema mapping + datetime parsing + `delay_minutes` calculation.
- `etl/load.py`: idempotent upsert into PostgreSQL (`ON CONFLICT (flight_id) DO UPDATE`).
- `backend/app/main.py`: FastAPI app setup, lifespan startup checks, CORS, structured request logging, global exception handling.
- `backend/app/database.py`: SQLAlchemy engine/session configuration and health connectivity checks.
- `backend/app/api/*.py`: API route modules for flights, airlines analytics, destinations, health, and flight-board SSE.

## 3. ETL Design

### Scheduling model
- Orchestrator: APScheduler (`BlockingScheduler`) in `etl/main.py`.
- Frequency: `SCHEDULE_INTERVAL_MINUTES` (default `15`).
- Behavior:
1. Run once immediately at process start.
2. Continue periodic runs on fixed interval.
3. Graceful shutdown on `SIGTERM`/`SIGINT`.

### ETL stages
1. **Extract**
   - Source: CKAN datastore endpoint (`CKAN_BASE_URL`, `CKAN_RESOURCE_ID`).
   - Method: pagination until empty batch.
2. **Transform**
   - Renames source columns to internal names.
   - Parses scheduled/actual timestamps.
   - Computes `delay_minutes`.
3. **Load**
   - Computes deterministic `flight_id` from natural keys (MD5).
   - Ensures `flights` table exists.
   - Upserts rows into PostgreSQL.

## 4. API Design

### Base app behavior
- Framework: FastAPI.
- Docs: `/docs`, `/redoc`, `/openapi.json`.
- Health/readiness endpoints: `/health`, `/ready`, `/metrics`.
- Startup gate: app fails startup if DB connectivity check fails.

### Endpoint groups (current)
- `GET /api/v1/flights/*`
  - Flight listing with pagination and filters.
  - Supporting lists (airlines, destinations).
- `GET /api/v1/airlines/*`
  - KPI aggregations (`/stats`, `/top-bottom`).
  - Destination analytics and health endpoint.
- `GET /api/v1/destinations/*`
  - Destination list, city autocomplete, airline performance by city.
- `GET /api/v1/flight-board/stream`
  - Server-Sent Events stream (rolling window, keepalive heartbeats).
- `GET /api/v1/flight-board/options`
  - Dropdown/filter values for the board UI.

## 5. Data Storage

### PostgreSQL (`flights` table)
Primary columns used by API and analytics:
- Identity and keys: `flight_id`, `airline_code`, `flight_number`, `direction`.
- Timing: `scheduled_time`, `actual_time`, `delay_minutes`, `scrape_timestamp`.
- Location: `location_iata`, `location_en`, `location_he`, `location_city_en`, `country_en`, `country_he`.
- Operational fields: `terminal`, `checkin_counters`, `checkin_zone`, `status_en`, `status_he`.

### Consistency model
- ETL writes are idempotent by `flight_id`.
- API is read-only against PostgreSQL.
- Frontend never writes directly to the DB.

## 6. Deployment Modes

### Default/current runtime
- ETL and backend services run as containers.
- PostgreSQL is either:
  - local container (e.g., `docker-compose-prod.yml`), or
  - managed service (e.g., Railway `DATABASE_URL`).

### Legacy/alternate assets
- `airflow/` contains older orchestration artifacts and utilities.
- Airflow is not required for the current default APScheduler-based pipeline.

## 7. Operational Controls

### Observability
- Structured logging (`structlog`) in backend.
- Request start/completion logs include status and process time.
- Health/readiness endpoints support service monitoring.

### Configuration
- Backend DB config supports either `DATABASE_URL` or explicit DB env vars.
- ETL supports either `DATABASE_URL` or ETL-specific PG env vars.
- CORS controlled with `CORS_ORIGINS` (comma-separated).

## 8. Known Constraints
- ETL is a single-process scheduler (no distributed orchestration).
- SSE board pushes full window snapshots every refresh interval.
- Some code paths/fields retain legacy naming (for backward compatibility).

## 9. Changelog Note
Updated for current architecture:
- APScheduler ETL (current)
- Direct ETL -> PostgreSQL flow
- Flight board SSE endpoints
- Airflow marked as legacy/optional
