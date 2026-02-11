# Architecture Migration: Airflow → Lightweight ETL Runner

## Notice

This project has migrated from Apache Airflow to a lightweight Python-based ETL runner using APScheduler.

## What Changed

### Before (Airflow-based)
- Heavy orchestration framework (Apache Airflow)
- Multiple containers (webserver, scheduler, database)
- Web UI on port 8082
- Complex setup and configuration
- DAG-based task orchestration

### After (ETL Runner)
- Lightweight Python scheduler (APScheduler)
- Single container (`etl` service)
- No web UI (logs via Docker)
- Simple configuration via environment variables
- Direct Python function calls

## Updated Architecture

```
CKAN API → ETL Runner (APScheduler) → PostgreSQL → FastAPI → React (Vercel)
```

## Service Changes

| Old Service | New Service | Notes |
|------------|-------------|-------|
| `airflow-webserver` | Removed | No longer needed |
| `airflow-scheduler` | Replaced by `etl` | Lightweight scheduler |
| `postgres_airflow` | Removed | ETL runner doesn't need metadata DB |
| `postgres_flights` | ✅ Unchanged | Still stores flight data |
| `backend` | ✅ Unchanged | Still serves API |
| `frontend` | Moved to Vercel | Now deployed separately |

## Port Changes

| Service | Old Port | New Port |
|---------|----------|----------|
| Airflow UI | 8082 | N/A (removed) |
| Backend API | 8000 | 8000 (unchanged) |
| Frontend | 80/3000 | Vercel URL |
| PostgreSQL (flights) | 5433 | 5433 (unchanged) |

## Configuration Changes

### Removed Variables
All `AIRFLOW_*` and `POSTGRES_AIRFLOW_*` variables have been removed from `.env` files.

### New Variables
- `SCHEDULE_INTERVAL_MINUTES` - ETL run frequency (default: 15)
- `CKAN_BASE_URL` - CKAN API endpoint
- `CKAN_RESOURCE_ID` - Resource identifier
- `CKAN_BATCH_SIZE` - Records per API call

## Monitoring Changes

### Before (Airflow)
- Access Airflow UI at `http://localhost:8082`
- View DAG runs and task logs in web interface
- Manage tasks through UI

### After (ETL Runner)
- View logs: `docker compose logs -f etl`
- Check status: `docker compose ps etl`
- Monitor via container logs and backend API health checks

## Benefits of Migration

1. **Simpler Deployment**: Fewer moving parts, easier to deploy and maintain
2. **Lower Resource Usage**: Single lightweight container vs. multiple Airflow services
3. **Faster Startup**: No Airflow initialization overhead
4. **Easier Debugging**: Direct Python logs, no abstraction layers
5. **Lower Complexity**: No DAG definitions or Airflow concepts to learn

## Documentation Status

⚠️ **Note**: Some documentation files may still reference Airflow from the previous architecture. When encountering Airflow references:

- Replace "Airflow" with "ETL Runner"
- Replace "DAG" with "scheduled pipeline"
- Replace "Airflow task" with "ETL function"
- Ignore references to Airflow UI or port 8082
- Use `docker compose logs etl` instead of Airflow UI for monitoring

## Updated Documentation

The following files have been updated to reflect the new architecture:
- ✅ `DEPLOYMENT.md` - Deployment guide
- ✅ `README.md` - Project overview
- ✅ `.env.prod.example` - Production environment template
- ✅ `env.example` - Development environment template

## Files Pending Update

The following documentation files still contain Airflow references and should be consulted with the understanding that "Airflow" refers to the new ETL Runner:
- `docs/PROJECT_GUIDE.md`
- `docs/guides/PROJECT_GUIDE.md`
- `docs/services/SERVICES_SUMMARY.md`
- `docs/architecture/SYSTEM_ARCHITECTURE_DIAGRAM.md`
- `docs/architecture/BACKEND_SYSTEM_DESIGN.md`
- `docs/architecture/DATA_FLOW_DIAGRAM.md`
- `docs/planning/PROJECT_TASKS.md`

## Getting Help

For questions about the new architecture:
1. Refer to `DEPLOYMENT.md` for deployment instructions
2. Check `docker-compose.yaml` and `docker-compose-prod.yml` for service definitions
3. Review `etl/main.py` for ETL runner implementation
4. View ETL logs: `docker compose logs -f etl`

Last updated: 2026-02-07
