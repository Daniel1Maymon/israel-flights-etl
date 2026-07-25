# System Architecture Diagram - Israel Flights ETL

## Overview
Current architecture and service boundaries for the active runtime.

```text
                          +-----------------------------+
                          |  CKAN API (data.gov.il)    |
                          |  datastore_search endpoint  |
                          +--------------+--------------+
                                         |
                                         | HTTP (paginated fetch)
                                         v
+---------------------------------------------------------------+
| ETL Service (`etl/main.py`)                                   |
| - APScheduler interval job (default every 15 min)             |
| - Extract: `etl/fetch.py`                                     |
| - Transform: `etl/transform.py`                               |
| - Load: `etl/load.py` (upsert by `flight_id`)                 |
+-------------------------------+-------------------------------+
                                |
                                | SQL write/upsert
                                v
+---------------------------------------------------------------+
| PostgreSQL (`flights` table)                                  |
| - Canonical cleaned data for serving + analytics              |
+-------------------------------+-------------------------------+
                                ^
                                | SQL read
+-------------------------------+-------------------------------+
| FastAPI Backend (`backend/app/main.py`)                       |
| - Health: `/`, `/health`, `/ready`, `/metrics`                |
| - Flights: `/api/v1/flights/*`                                |
| - Airlines KPIs: `/api/v1/airlines/*`                         |
| - Destinations: `/api/v1/destinations/*`                      |
| - Flight board SSE: `/api/v1/flight-board/stream`             |
+-------------------------------+-------------------------------+
                                |
                                | HTTP/JSON + SSE
                                v
+---------------------------------------------------------------+
| Frontend Clients (React dashboard + browser consumers)        |
+---------------------------------------------------------------+
```

## Deployment Notes
- `docker-compose-prod.yml`: full local stack (includes PostgreSQL).
- `docker-compose.yml`: Railway-oriented composition; expects managed DB (`DATABASE_URL`).
- `airflow/` folder exists as legacy/alternate orchestration assets, not required for current runtime.
