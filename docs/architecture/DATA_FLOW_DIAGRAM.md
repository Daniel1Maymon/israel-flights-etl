# Data Flow Diagram - Israel Flights ETL

## End-to-End Flow (Current)

```text
CKAN API
  -> ETL Extract (fetch all pages)
  -> ETL Transform (map fields, parse datetimes, compute delay)
  -> ETL Load (upsert to PostgreSQL)
  -> FastAPI queries
  -> JSON/SSE responses
  -> Frontend visualization
```

## Detailed Pipeline

### 1. Extract
- Module: `etl/fetch.py`
- Input: CKAN API endpoint + resource ID.
- Logic: page through records using `offset += batch_size` until empty result.
- Output: list of raw record dictionaries in memory.

### 2. Transform
- Module: `etl/transform.py`
- Input: raw CKAN records.
- Logic:
  - rename source fields (`CH*`) to internal names,
  - parse scheduled/actual timestamps,
  - calculate `delay_minutes`.
- Output: normalized pandas DataFrame.

### 3. Load
- Module: `etl/load.py`
- Input: transformed DataFrame.
- Logic:
  - compute deterministic `flight_id` from natural key,
  - create `flights` table if needed,
  - bulk upsert with conflict update.
- Output: committed rows in PostgreSQL.

### 4. Serve
- Modules: `backend/app/api/*.py`
- Input: SQLAlchemy/SQL queries against `flights`.
- Output:
  - paginated/filterable REST JSON,
  - airline KPI aggregations,
  - destination analytics,
  - flight-board SSE snapshots + heartbeats.

## Operational Timing
- ETL interval: `SCHEDULE_INTERVAL_MINUTES` (default 15).
- Flight-board stream refresh: every 900 seconds with 10-second keepalive comments.

## Error Handling Path
- Extract failure: ETL run logs exception; next scheduled run continues.
- Transform/load failure: current ETL cycle fails; process remains alive unless fatal.
- API failure: FastAPI global handler returns structured 500 response.
- DB readiness failure: FastAPI startup fails fast.

## Legacy Note
Older docs/assets reference Airflow + S3 stages. Current default runtime is direct ETL -> PostgreSQL without S3 dependency.
