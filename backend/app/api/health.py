"""
Health and status endpoints
"""
from fastapi import APIRouter
import structlog

logger = structlog.get_logger()

router = APIRouter(tags=["health"])


@router.get(
    "/",
    summary="API Root",
    description="API root endpoint"
)
async def root():
    """API root endpoint"""
    from app.config import settings
    return {
        "message": "Israel Flights API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }


@router.get(
    "/health",
    summary="Health check",
    description="Basic health check endpoint"
)
async def health_check():
    """Basic health check endpoint"""
    import time
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }


@router.get(
    "/ready",
    summary="Readiness check",
    description="Readiness check including database connectivity"
)
async def readiness_check():
    """Readiness check including database connectivity"""
    from app.database import check_db_connection
    
    # Check database connection
    db_healthy = check_db_connection()
    
    if not db_healthy:
        return {
            "status": "not_ready",
            "database": "unhealthy",
            "timestamp": time.time()
        }
    
    return {
        "status": "ready",
        "database": "healthy",
        "timestamp": time.time()
    }


@router.get(
    "/metrics",
    summary="Basic metrics",
    description="Basic application metrics"
)
async def metrics():
    """Basic application metrics"""
    import time
    return {
        "timestamp": time.time(),
        "uptime": "running",
        "version": "1.0.0"
    }
