from typing import Generator
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
import structlog

from app.database import get_db, check_db_connection
from app.config import settings

logger = structlog.get_logger()


def get_database() -> Generator[Session, None, None]:
    """Dependency to get database session with health check"""
    db = next(get_db())
    
    # Check database connection health
    if not check_db_connection():
        logger.error("Database connection unhealthy")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    try:
        yield db
    except Exception as e:
        logger.error("Database session error", error=str(e))
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    finally:
        db.close()


def validate_page_size(size: int) -> int:
    """Validate and limit page size"""
    if size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be at least 1"
        )
    
    if size > settings.max_page_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page size cannot exceed {settings.max_page_size}"
        )
    
    return size


def validate_page_number(page: int) -> int:
    """Validate page number"""
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be at least 1"
        )
    
    return page
