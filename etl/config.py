import os
from urllib.parse import urlparse


def parse_database_url(database_url: str) -> dict:
    """
    Parse DATABASE_URL into individual connection parameters.
    Format: postgresql://user:password@host:port/database
    """
    parsed = urlparse(database_url)
    return {
        "pg_host": parsed.hostname or "localhost",
        "pg_port": parsed.port or 5432,
        "pg_database": parsed.path.lstrip("/") if parsed.path else "flights_db",
        "pg_user": parsed.username or "daniel",
        "pg_password": parsed.password or "daniel",
    }


def get_config() -> dict:
    """
    Load ETL configuration from environment variables with defaults.
    Supports both DATABASE_URL (Railway) and individual variables (local).

    Railway Private Networking:
    - BACKEND_PRIVATE_URL: Backend service private URL (e.g., http://backend.railway.internal:8000)
    - If not set, ETL communicates directly with database
    """
    # Check if DATABASE_URL is provided (Railway deployment)
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Parse DATABASE_URL for Railway/Heroku-style deployment
        db_config = parse_database_url(database_url)
    else:
        # Fall back to individual environment variables for local development
        db_config = {
            "pg_host": os.getenv("POSTGRES_FLIGHTS_HOST") or "postgres_flights",
            "pg_port": int(os.getenv("POSTGRES_FLIGHTS_PORT") or 5432),
            "pg_database": os.getenv("POSTGRES_FLIGHTS_DB") or "flights_db",
            "pg_user": os.getenv("POSTGRES_FLIGHTS_USER") or "daniel",
            "pg_password": os.getenv("POSTGRES_FLIGHTS_PASSWORD") or "daniel",
        }

    # Railway Private Networking support
    # BACKEND_PRIVATE_URL should be set to backend's Railway private domain
    # Format: http://<service-name>.railway.internal:<port>
    backend_url = os.getenv("BACKEND_PRIVATE_URL")

    return {
        "ckan_base_url": os.getenv("CKAN_BASE_URL") or "https://data.gov.il/api/3/action/datastore_search",
        "ckan_resource_id": os.getenv("CKAN_RESOURCE_ID") or "e83f763b-b7d7-479e-b172-ae981ddc6de5",
        "ckan_batch_size": int(os.getenv("CKAN_BATCH_SIZE") or 1000),
        "schedule_interval_minutes": int(os.getenv("SCHEDULE_INTERVAL_MINUTES") or 15),
        "backend_url": backend_url,  # Optional: for ETL to trigger backend endpoints
        **db_config,
    }
