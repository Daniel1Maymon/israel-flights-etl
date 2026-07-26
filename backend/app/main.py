from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time
from contextlib import asynccontextmanager

from app.config import settings
from app.database import check_db_connection
from app.api.router import api_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.schemas.flight import ErrorResponse

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Israel Flights API", version=settings.api_version)
    
    # Check database connection
    if not check_db_connection():
        logger.error("Database connection failed during startup")
        raise RuntimeError("Database connection failed")

    # Create/migrate the AI counter + event tables ONCE, here.
    # These blocks ALTER tables (AccessExclusiveLock); running them per request let two
    # gunicorn workers deadlock against each other while serving the admin dashboard.
    # run_ddl serialises workers via a Postgres advisory lock.
    try:
        from app.database import engine
        from app.services.ai_flags import ensure_flags_table
        from app.services.analytics import ensure_events_table
        from app.services.ratelimit import ensure_tables

        ensure_tables(engine)
        ensure_events_table(engine)
        ensure_flags_table(engine)
    except Exception as exc:
        # Non-fatal: the tables normally already exist, and the API must still serve
        # flight data if only the AI-search bookkeeping is unavailable.
        logger.warning("schema initialisation failed", error=str(exc))

    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Israel Flights API")


# Create FastAPI application.
# The OpenAPI schema enumerates every route, query parameter and response model, so it
# is not published unless ENABLE_API_DOCS is explicitly set.
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

# --- Rate limiting -----------------------------------------------------------------
# The row caps bound the cost of ONE request; this bounds requests per client per minute.
# Applied as middleware so it covers every route, including ones added later, rather
# than requiring an opt-in decorator per endpoint.
#
# /health is exempt so platform uptime probes cannot be starved by other traffic sharing
# an address. It is a cheap endpoint, so the trade is small.
app.add_middleware(
    RateLimitMiddleware,
    limit=settings.rate_limit_per_minute,
    window_seconds=60,
    exempt_paths={"/health"},
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # needed for the rankair_uid cookie (per-user AI-search limits)
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all requests and responses"""
    start_time = time.time()
    
    # Log request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=process_time
    )
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(
        "Unhandled exception",
        method=request.method,
        url=str(request.url),
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "details": {"error": "Please try again later"}
            }
        ).model_dump()
    )


# Include all API endpoints
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
