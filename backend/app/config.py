import os
from typing import List
from urllib.parse import urlparse
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "flights_db"
    db_user: str = "daniel"
    db_password: str = ""
    postgres_flights_host: str | None = None
    postgres_flights_port: int | None = None
    postgres_flights_db: str | None = None
    postgres_flights_user: str | None = None
    postgres_flights_password: str | None = None
    
    @property
    def database_url(self) -> str:
        """Build database URL from individual components"""
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Normalize Railway/Heroku-style URLs for SQLAlchemy
            if database_url.startswith("postgres://"):
                return database_url.replace("postgres://", "postgresql+psycopg://", 1)
            if database_url.startswith("postgresql://"):
                return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return database_url
        # Support shared ETL-style env naming used in project root .env
        pg_host = self.postgres_flights_host
        pg_port = self.postgres_flights_port
        pg_db = self.postgres_flights_db
        pg_user = self.postgres_flights_user
        pg_password = self.postgres_flights_password
        if all([pg_host, pg_port, pg_db, pg_user, pg_password]):
            return f"postgresql+psycopg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Israel Flights API"
    api_version: str = "1.0.0"
    api_description: str = "API for Israeli flight data from ETL pipeline"
    
    # CORS settings
    # Can be set via CORS_ORIGINS environment variable (comma-separated)
    # Default includes common localhost ports for development
    # For production, set CORS_ORIGINS to your Vercel URL: https://your-app.vercel.app
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081,http://localhost:8082,http://127.0.0.1:8082,http://localhost:8083,http://127.0.0.1:8083,http://localhost:5173,http://127.0.0.1:5173,http://localhost,http://127.0.0.1"

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Parse CORS origins from comma-separated string.

        Railway deployment: Set CORS_ORIGINS environment variable to:
        - Vercel frontend URL: https://your-app.vercel.app
        - Multiple origins: https://your-app.vercel.app,https://your-app-preview.vercel.app

        The backend will allow requests from these origins.
        """
        if isinstance(self.cors_origins, str):
            origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
            # Also support Railway's internal network (for ETL service communication)
            railway_internal = os.getenv("RAILWAY_PRIVATE_DOMAIN")
            if railway_internal:
                origins.append(f"http://{railway_internal}")
                origins.append(f"https://{railway_internal}")
            return origins
        return self.cors_origins if isinstance(self.cors_origins, list) else []
    
    # Pagination settings
    default_page_size: int = 20
    max_page_size: int = 50

    # --- Response bounds -------------------------------------------------------
    # Hard ceiling on rows in any public response. Every data path must honour this:
    # it is what makes response cost independent of what the client asks for.
    max_public_rows: int = 100
    # Widest date span the flight board will query. The row cap bounds the response;
    # this bounds the work Postgres does before the LIMIT can discard anything.
    max_board_window_days: int = 31
    # Deepest OFFSET a client may reach. OFFSET n makes Postgres materialise and
    # discard n sorted rows, so deep pages are the most expensive requests in the API.
    max_offset: int = 10_000
    # How far back /flight-board/options looks when building filter dropdowns.
    options_horizon_days: int = 90
    # How far back the board will serve RAW per-flight rows. The archive is built by a
    # year of daily collection and cannot be re-derived from the IAA feed (rolling 4-day
    # window), so raw history is withheld; aggregates still cover the full range.
    board_history_days: int = 30
    # Concurrent SSE connections. Long-lived, so a per-minute rate limit cannot bound them.
    max_sse_connections: int = 50
    sse_query_threads: int = 4
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Security
    # Empty defaults are deliberate: a working default lets a misconfigured deploy start
    # successfully and run on a value that is public in this file. See _require_prod_secrets.
    secret_key: str = ""
    access_token_expire_minutes: int = 30

    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 20
    # NOTE: counters are per-process (see app/middleware/rate_limit.py). With workers > 1
    # the effective limit is rate_limit_per_minute * workers. `workers` is 1 today; raise
    # it and the limiter needs a shared backend before the number below means anything.
    # Publish /docs, /redoc, /openapi.json. Off by default: the schema lists every route,
    # every query parameter, and every response model.
    enable_api_docs: bool = False
    
    # Monitoring
    sentry_dsn: str = ""
    prometheus_enabled: bool = True
    health_check_timeout: int = 30
    
    # Caching
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300
    
    # Performance
    workers: int = 1
    max_connections: int = 100
    keep_alive_timeout: int = 5

    # AI search (natural-language query feature) — provider-agnostic LLM layer
    llm_provider: str = "gemini"                   # LLM_PROVIDER: gemini | openai
    llm_model: str = "gemini-2.5-flash"            # LLM_MODEL: any model id for the chosen provider
    gemini_api_key: str = ""                        # GEMINI_API_KEY
    openai_api_key: str = ""                        # OPENAI_API_KEY
    database_url_ro: str = ""                       # DATABASE_URL_RO — read-only rankair_ro role
    ai_daily_limit_per_user: int = 10               # questions per user per day
    ai_monthly_budget_tokens: int = 20_000_000      # global monthly token ceiling (~$6-8 Flash)
    ai_max_question_chars: int = 500                # reject longer questions pre-call
    ai_max_rows: int = 50                           # forced LIMIT on all AI queries

    # Admin analytics dashboard — Bearer token guarding GET /api/v1/admin/*.
    # Fail-closed: if unset, all admin endpoints return 401.
    admin_token: str = ""                           # ADMIN_TOKEN

    @model_validator(mode="after")
    def _require_prod_secrets(self) -> "Settings":
        """
        Fail closed in production rather than booting on a placeholder.

        A missing secret should crash at startup, where it is loud, instead of running
        for months on a value committed to this file. Mirrors how admin_token already
        behaves (unset -> every admin request 401s).
        """
        if not os.getenv("RAILWAY_ENVIRONMENT"):
            return self  # local/dev: defaults are fine
        missing: list[str] = []
        # SECRET_KEY is deliberately NOT required: nothing reads it (no JWT/session
        # code exists yet), so refusing to boot over it would be a self-inflicted
        # outage protecting nothing. Add it here the moment it is actually used --
        # signing with an empty or placeholder key is the failure worth blocking.
        #
        # DATABASE_URL carries its own credentials, so db_password is only required
        # when the URL is being assembled from parts.
        if not os.getenv("DATABASE_URL") and not self.postgres_flights_password:
            if not self.db_password:
                missing.append("DB_PASSWORD")
        if missing:
            raise ValueError(
                f"Refusing to start: {', '.join(missing)} must be set in production."
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
