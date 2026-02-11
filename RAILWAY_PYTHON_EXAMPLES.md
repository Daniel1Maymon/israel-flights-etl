# Railway Private Networking - Python Code Examples

This document provides exact Python code snippets for reading Railway environment variables dynamically.

## Table of Contents
1. [ETL Reading Backend URL](#etl-reading-backend-url)
2. [Backend CORS Configuration](#backend-cors-configuration)
3. [Database Connection](#database-connection)
4. [Complete ETL Integration Example](#complete-etl-integration-example)

---

## ETL Reading Backend URL

### Basic Example - Reading Backend URL
```python
import os
import requests

# Read backend URL from environment variable
# Railway Private Networking format: http://backend.railway.internal:8000
backend_url = os.getenv("BACKEND_PRIVATE_URL")

if backend_url:
    print(f"✅ Backend URL configured: {backend_url}")

    # Test connection to backend
    try:
        response = requests.get(f"{backend_url}/health", timeout=5)
        response.raise_for_status()
        print("✅ Backend is reachable")
    except requests.RequestException as e:
        print(f"❌ Backend unreachable: {e}")
else:
    print("⚠️  BACKEND_PRIVATE_URL not set - ETL will only use database")
```

### ETL Config with Dynamic Backend URL
```python
# etl/config.py
import os
from urllib.parse import urlparse

def get_config() -> dict:
    """
    Load ETL configuration with Railway Private Networking support.
    """
    # Parse database URL
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)
        db_config = {
            "pg_host": parsed.hostname or "localhost",
            "pg_port": parsed.port or 5432,
            "pg_database": parsed.path.lstrip("/") if parsed.path else "flights_db",
            "pg_user": parsed.username or "daniel",
            "pg_password": parsed.password or "daniel",
        }
    else:
        db_config = {
            "pg_host": os.getenv("POSTGRES_FLIGHTS_HOST", "localhost"),
            "pg_port": int(os.getenv("POSTGRES_FLIGHTS_PORT", 5432)),
            "pg_database": os.getenv("POSTGRES_FLIGHTS_DB", "flights_db"),
            "pg_user": os.getenv("POSTGRES_FLIGHTS_USER", "daniel"),
            "pg_password": os.getenv("POSTGRES_FLIGHTS_PASSWORD", "daniel"),
        }

    # Read backend URL for Railway Private Networking
    backend_url = os.getenv("BACKEND_PRIVATE_URL")

    return {
        # CKAN API settings
        "ckan_base_url": os.getenv(
            "CKAN_BASE_URL",
            "https://data.gov.il/api/3/action/datastore_search"
        ),
        "ckan_resource_id": os.getenv(
            "CKAN_RESOURCE_ID",
            "e83f763b-b7d7-479e-b172-ae981ddc6de5"
        ),
        "ckan_batch_size": int(os.getenv("CKAN_BATCH_SIZE", 1000)),

        # Schedule settings
        "schedule_interval_minutes": int(os.getenv("SCHEDULE_INTERVAL_MINUTES", 15)),

        # Backend URL (Railway Private Network)
        "backend_url": backend_url,

        # Database config
        **db_config,
    }
```

### Using Backend URL in ETL Pipeline
```python
# etl/main.py
import logging
from etl.config import get_config
from etl.backend_client import BackendClient

logger = logging.getLogger(__name__)

def run_pipeline() -> None:
    """Execute ETL pipeline with optional backend communication."""
    cfg = get_config()

    # Initialize backend client (only if URL is configured)
    backend_client = BackendClient(cfg.get("backend_url"))

    # Check backend health before starting
    if backend_client.enabled and not backend_client.health_check():
        logger.warning("Backend is not reachable - continuing with database only")

    # Fetch data
    records = fetch_flights(
        base_url=cfg["ckan_base_url"],
        resource_id=cfg["ckan_resource_id"],
        batch_size=cfg["ckan_batch_size"],
    )

    if not records:
        logger.info("No records fetched")
        return

    # Transform data
    df = transform_records(records)

    # Load to database
    rows = load_to_db(df, cfg)
    logger.info("Pipeline complete - %d rows upserted", rows)

    # Notify backend (optional)
    if backend_client.enabled:
        backend_client.notify_etl_complete(rows)
        backend_client.trigger_cache_refresh()
```

---

## Backend CORS Configuration

### Reading CORS Origins from Environment
```python
# backend/app/config.py
import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # CORS settings
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Parse CORS origins from comma-separated environment variable.

        Railway Environment Variable:
            CORS_ORIGINS=https://your-app.vercel.app,https://preview.vercel.app

        This allows your Vercel frontend to make requests to Railway backend.
        """
        if isinstance(self.cors_origins, str):
            origins = [
                origin.strip()
                for origin in self.cors_origins.split(",")
                if origin.strip()
            ]

            # Add Railway internal domain (for ETL service)
            railway_domain = os.getenv("RAILWAY_PRIVATE_DOMAIN")
            if railway_domain:
                origins.append(f"http://{railway_domain}")
                origins.append(f"https://{railway_domain}")

            return origins
        return self.cors_origins if isinstance(self.cors_origins, list) else []

settings = Settings()
```

### FastAPI CORS Middleware Configuration
```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="Israel Flights API")

# Configure CORS with dynamic origins from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # Reads from CORS_ORIGINS env var
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Your routes here...
```

### Verifying CORS Configuration
```python
# backend/app/main.py - Add logging to verify CORS setup
import logging

logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Log CORS configuration on startup"""
    logger.info(f"CORS configured for origins: {settings.cors_origins_list}")

    # Expected output on Railway:
    # CORS configured for origins: ['https://your-app.vercel.app', 'http://backend.railway.internal']
```

---

## Database Connection

### Reading DATABASE_URL Dynamically
```python
import os
import psycopg
from urllib.parse import urlparse

def get_database_connection():
    """
    Connect to database using Railway-provided DATABASE_URL.

    Railway automatically injects: DATABASE_URL=postgresql://user:pass@host:port/db
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    try:
        conn = psycopg.connect(database_url)
        print(f"✅ Connected to database: {urlparse(database_url).hostname}")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise

# Usage
conn = get_database_connection()
```

### SQLAlchemy with Railway DATABASE_URL
```python
# backend/app/config.py
import os
from sqlalchemy import create_engine

class Settings(BaseSettings):
    @property
    def database_url(self) -> str:
        """
        Build database URL for SQLAlchemy.
        Railway provides: postgresql://... (postgres:// prefix)
        SQLAlchemy needs: postgresql+psycopg://...
        """
        database_url = os.getenv("DATABASE_URL")

        if database_url:
            # Normalize Railway/Heroku postgres:// to postgresql+psycopg://
            if database_url.startswith("postgres://"):
                return database_url.replace("postgres://", "postgresql+psycopg://", 1)
            if database_url.startswith("postgresql://"):
                return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return database_url

        # Fallback for local development
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

# Create engine
settings = Settings()
engine = create_engine(settings.database_url)
```

---

## Complete ETL Integration Example

### Full ETL Service with Backend Communication

```python
# etl/main.py - Complete integration
import logging
import signal
import sys
import os
from apscheduler.schedulers.blocking import BlockingScheduler

from etl.config import get_config
from etl.fetch import fetch_flights
from etl.transform import transform_records
from etl.load import load_to_db
from etl.backend_client import BackendClient

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    """
    Execute complete ETL pipeline with Railway Private Networking.

    Environment Variables (Railway):
        - DATABASE_URL: PostgreSQL connection (auto-injected by Railway)
        - BACKEND_PRIVATE_URL: Backend service URL (http://backend.railway.internal:8000)
        - SCHEDULE_INTERVAL_MINUTES: How often to run ETL
        - CKAN_BASE_URL: Israeli data API URL
        - CKAN_RESOURCE_ID: Dataset ID
    """
    cfg = get_config()

    # Initialize backend client with Railway Private URL
    backend_url = cfg.get("backend_url")
    backend_client = BackendClient(backend_url)

    logger.info("Starting ETL pipeline run")
    logger.info(f"Backend URL: {backend_url or 'Not configured'}")
    logger.info(f"Database: {cfg['pg_host']}:{cfg['pg_port']}/{cfg['pg_database']}")

    # Optional: Check backend health before processing
    if backend_client.enabled:
        if backend_client.health_check():
            logger.info("✅ Backend is healthy and reachable via private network")
        else:
            logger.warning("⚠️  Backend health check failed - continuing anyway")

    # Fetch data from CKAN API
    logger.info(f"Fetching from {cfg['ckan_base_url']}")
    records = fetch_flights(
        base_url=cfg["ckan_base_url"],
        resource_id=cfg["ckan_resource_id"],
        batch_size=cfg["ckan_batch_size"],
    )

    if not records:
        logger.info("No records fetched — skipping transform/load")
        return

    logger.info(f"Fetched {len(records)} records")

    # Transform data
    df = transform_records(records)
    logger.info(f"Transformed {len(df)} records")

    # Load to database
    rows = load_to_db(df, cfg)
    logger.info(f"✅ Pipeline complete — {rows} rows upserted")

    # Notify backend via Railway Private Network (optional)
    if backend_client.enabled:
        logger.info("Notifying backend via private network...")
        backend_client.notify_etl_complete(rows)
        backend_client.trigger_cache_refresh()


def main() -> None:
    """Entry point with Railway-compatible configuration."""
    cfg = get_config()
    interval = cfg["schedule_interval_minutes"]

    logger.info("=" * 60)
    logger.info("Israel Flights ETL Service (Railway Deployment)")
    logger.info("=" * 60)
    logger.info(f"Schedule: Every {interval} minutes")
    logger.info(f"Backend: {cfg.get('backend_url') or 'Not configured'}")
    logger.info(f"Database: {cfg['pg_host']}:{cfg['pg_port']}")
    logger.info("=" * 60)

    # Run immediately on startup
    try:
        run_pipeline()
    except Exception:
        logger.exception("Initial pipeline run failed")

    # Schedule recurring runs
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "interval", minutes=interval)
    logger.info(f"✅ Scheduled pipeline to run every {interval} minutes")

    # Graceful shutdown handler
    def _shutdown(signum, frame):
        logger.info(f"Received signal {signum} — shutting down gracefully")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start scheduler (blocking)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("ETL service stopped")


if __name__ == "__main__":
    main()
```

---

## Environment Variables Summary

### Railway Backend Service
```bash
# Set these in Railway Dashboard → Backend Service → Variables

# Database (auto-injected if using Railway Postgres)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# CORS - Your Vercel frontend URL
CORS_ORIGINS=https://your-app.vercel.app,https://preview-*.vercel.app

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### Railway ETL Service
```bash
# Set these in Railway Dashboard → ETL Service → Variables

# Database (reference backend's or direct)
DATABASE_URL=${{backend.DATABASE_URL}}

# Backend Private URL - Critical for Railway Private Networking
BACKEND_PRIVATE_URL=http://backend.railway.internal:8000

# ETL Configuration
SCHEDULE_INTERVAL_MINUTES=15
CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search
CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5
CKAN_BATCH_SIZE=1000
LOG_LEVEL=INFO
```

### Vercel Frontend
```bash
# Set these in Vercel Dashboard → Settings → Environment Variables

# Backend PUBLIC URL (not private URL!)
NEXT_PUBLIC_API_URL=https://your-backend-service.railway.app
```

---

## Testing Railway Private Networking

### Test Script (Run in ETL Service)
```python
# test_railway_private_network.py
import os
import requests
import psycopg

def test_backend_connection():
    """Test ETL → Backend communication via Railway Private Network"""
    backend_url = os.getenv("BACKEND_PRIVATE_URL")

    if not backend_url:
        print("❌ BACKEND_PRIVATE_URL not set")
        return False

    print(f"Testing backend at: {backend_url}")

    try:
        response = requests.get(f"{backend_url}/health", timeout=10)
        response.raise_for_status()
        print(f"✅ Backend reachable: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Backend unreachable: {e}")
        return False


def test_database_connection():
    """Test database connection via DATABASE_URL"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not set")
        return False

    try:
        conn = psycopg.connect(database_url)
        print("✅ Database connected")

        # Test query
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM flights;")
            count = cur.fetchone()[0]
            print(f"✅ Flights table has {count} records")

        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Railway Private Networking Test")
    print("=" * 60)

    backend_ok = test_backend_connection()
    database_ok = test_database_connection()

    print("=" * 60)
    if backend_ok and database_ok:
        print("✅ All connections successful!")
    else:
        print("❌ Some connections failed - check logs")
    print("=" * 60)
```

Run this script in Railway to verify private networking works correctly.

---

## Key Takeaways

1. **Use `os.getenv()` for all configuration**
   - Railway injects environment variables automatically
   - No hardcoded URLs or credentials

2. **Private Network Format**
   - Backend: `http://backend.railway.internal:8000`
   - ETL → Backend: Use private URL (faster, free, secure)
   - Frontend → Backend: Use public URL (`*.railway.app`)

3. **CORS Must Allow Vercel**
   - Set `CORS_ORIGINS=https://your-app.vercel.app` in backend
   - Backend automatically reads this via `os.getenv("CORS_ORIGINS")`

4. **Database Sharing**
   - Both services use same `DATABASE_URL`
   - Reference across services: `${{backend.DATABASE_URL}}`

5. **Error Handling**
   - Always check if URLs are configured before using
   - Graceful degradation if backend is unreachable
   - Log all connection attempts for debugging

---

## Additional Resources

- [Railway Private Networking Docs](https://docs.railway.app/reference/private-networking)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [Vercel Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)
