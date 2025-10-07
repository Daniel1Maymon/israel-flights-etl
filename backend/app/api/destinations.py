"""
Destinations endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.models.flight import Flight

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["destinations"])


@router.get(
    "/destinations",
    summary="List all destinations",
    description="Get list of all unique destinations for filter dropdown"
)
async def list_destinations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: Optional[str] = Query(None, description="Search destination name"),
    db: Session = Depends(get_db)
):
    """Get all unique destinations for filter dropdown"""
    try:
        # Get unique destinations
        query = db.query(Flight.location_en).distinct()
        
        # Apply search filter
        if search:
            query = query.filter(Flight.location_en.ilike(f"%{search}%"))
        
        # Get total count
        total_count = query.count()
        
        # Calculate pagination
        offset = (page - 1) * size
        total_pages = (total_count + size - 1) // size
        
        # Get destinations
        destinations = query.offset(offset).limit(size).all()
        
        # Convert to response format
        destination_data = []
        for dest in destinations:
            destination_data.append({
                "destination": dest.location_en
            })
        
        return {
            "destinations": destination_data,
            "total_count": total_count,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "has_more": page < total_pages
        }
        
    except Exception as e:
        logger.error("Error retrieving destinations", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve destinations"
        )

