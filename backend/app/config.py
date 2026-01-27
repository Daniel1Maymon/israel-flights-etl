import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database settings
    db_host: str = "localhost"
    db_port: int = 5433  # Changed to 5433 to match Airflow's postgres_flights
    db_name: str = "flights_db"
    db_user: str = "daniel"
    db_password: str = "daniel"
    
    @property
    def database_url(self) -> str:
        """Build database URL from individual components"""
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
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081,http://localhost:8082,http://127.0.0.1:8082,http://localhost:8083,http://127.0.0.1:8083,http://localhost:5173,http://127.0.0.1:5173,http://localhost,http://127.0.0.1"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins if isinstance(self.cors_origins, list) else []
    
    # Pagination settings
    default_page_size: int = 50
    max_page_size: int = 200
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    
    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 20
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
