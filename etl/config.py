import os


def get_config() -> dict:
    """Load ETL configuration from environment variables with defaults."""
    return {
        "ckan_base_url": os.getenv("CKAN_BASE_URL") or "https://data.gov.il/api/3/action/datastore_search",
        "ckan_resource_id": os.getenv("CKAN_RESOURCE_ID") or "e83f763b-b7d7-479e-b172-ae981ddc6de5",
        "ckan_batch_size": int(os.getenv("CKAN_BATCH_SIZE") or 1000),
        "schedule_interval_minutes": int(os.getenv("SCHEDULE_INTERVAL_MINUTES") or 15),
        "pg_host": os.getenv("POSTGRES_FLIGHTS_HOST") or "postgres_flights",
        "pg_port": int(os.getenv("POSTGRES_FLIGHTS_PORT") or 5432),
        "pg_database": os.getenv("POSTGRES_FLIGHTS_DB") or "flights_db",
        "pg_user": os.getenv("POSTGRES_FLIGHTS_USER") or "daniel",
        "pg_password": os.getenv("POSTGRES_FLIGHTS_PASSWORD") or "daniel",
    }
