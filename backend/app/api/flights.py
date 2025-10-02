"""
Flight data endpoints
"""
from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import structlog

from app.database import get_db
from app.models.flight import Flight

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/flights", tags=["flights"])


@router.get(
    "/",
    summary="List flights",
    description="Get list of flights with pagination and filtering"
)
async def list_flights(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    direction: Optional[str] = Query(None, description="Filter by direction (A=Arrival, D=Departure)"),
    airline_code: Optional[str] = Query(None, description="Filter by airline code"),
    status: Optional[str] = Query(None, description="Filter by status"),
    terminal: Optional[str] = Query(None, description="Filter by terminal"),
    date_from: Optional[date] = Query(None, description="Filter flights from date"),
    date_to: Optional[date] = Query(None, description="Filter flights to date"),
    delay_min: Optional[int] = Query(None, ge=0, description="Minimum delay in minutes"),
    delay_max: Optional[int] = Query(None, ge=0, description="Maximum delay in minutes"),
    sort_by: Optional[str] = Query("scheduled_time", description="Sort field"),
    sort_order: Optional[str] = Query("asc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db)
):
    """Get list of flights with pagination and filtering"""
    try:
        logger.info("Starting flight query", page=page, size=size)
        
        # Build base query
        query = db.query(Flight)
        
        # Apply filters
        if direction:
            query = query.filter(Flight.direction == direction)
        if airline_code:
            query = query.filter(Flight.airline_code == airline_code)
        if status:
            query = query.filter(Flight.status_en.ilike(f"%{status}%"))
        if terminal:
            query = query.filter(Flight.terminal == terminal)
        if date_from:
            query = query.filter(Flight.scheduled_time >= date_from)
        if date_to:
            query = query.filter(Flight.scheduled_time <= date_to)
        if delay_min is not None:
            query = query.filter(Flight.delay_minutes >= delay_min)
        if delay_max is not None:
            query = query.filter(Flight.delay_minutes <= delay_max)
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        if sort_by == "scheduled_time":
            if sort_order == "desc":
                query = query.order_by(Flight.scheduled_time.desc())
            else:
                query = query.order_by(Flight.scheduled_time.asc())
        elif sort_by == "airline_name":
            if sort_order == "desc":
                query = query.order_by(Flight.airline_name.desc())
            else:
                query = query.order_by(Flight.airline_name.asc())
        elif sort_by == "location_en":
            if sort_order == "desc":
                query = query.order_by(Flight.location_en.desc())
            else:
                query = query.order_by(Flight.location_en.asc())
        elif sort_by == "delay_minutes":
            if sort_order == "desc":
                query = query.order_by(Flight.delay_minutes.desc())
            else:
                query = query.order_by(Flight.delay_minutes.asc())
        else:
            # Default sorting
            query = query.order_by(Flight.scheduled_time.desc())
        
        # Apply pagination
        offset = (page - 1) * size
        flights = query.offset(offset).limit(size).all()
        
        # Calculate pagination info
        total_pages = (total_count + size - 1) // size
        has_next = page < total_pages
        has_prev = page > 1
        
        # Convert to response format
        flight_data = []
        for flight in flights:
            flight_data.append({
                "flight_id": flight.flight_id,
                "flight_number": flight.flight_number,
                "airline_code": flight.airline_code,
                "airline_name": flight.airline_name,
                "direction": flight.direction,
                "location_iata": flight.location_iata,
                "scheduled_time": flight.scheduled_time.isoformat() if flight.scheduled_time else None,
                "actual_time": flight.actual_time.isoformat() if flight.actual_time else None,
                "location_en": flight.location_en,
                "location_he": flight.location_he,
                "location_city_en": flight.location_city_en,
                "country_en": flight.country_en,
                "country_he": flight.country_he,
                "terminal": flight.terminal,
                "checkin_counters": flight.checkin_counters,
                "checkin_zone": flight.checkin_zone,
                "status_en": flight.status_en,
                "status_he": flight.status_he,
                "delay_minutes": flight.delay_minutes,
                "scrape_timestamp": flight.scrape_timestamp.isoformat() if flight.scrape_timestamp else None,
                "raw_s3_path": flight.raw_s3_path
            })
        
        logger.info("Successfully processed flights", 
                   total_count=total_count, 
                   returned_count=len(flight_data),
                   page=page,
                   total_pages=total_pages)
        
        return {
            "data": flight_data,
            "pagination": {
                "page": page,
                "size": size,
                "total": total_count,
                "pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
        
    except Exception as e:
        logger.error("Error retrieving flights", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve flights"
        )


@router.get(
    "/airlines",
    summary="List airlines",
    description="Get list of unique airlines for filter dropdown"
)
async def list_airlines(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: Optional[str] = Query(None, description="Search airline name or code"),
    db: Session = Depends(get_db)
):
    """Get list of unique airlines for filter dropdown"""
    try:
        # Get unique airlines
        query = db.query(Flight.airline_code, Flight.airline_name).distinct()
        
        # Apply search filter
        if search:
            query = query.filter(
                or_(
                    Flight.airline_code.ilike(f"%{search}%"),
                    Flight.airline_name.ilike(f"%{search}%")
                )
            )
        
        # Get total count
        total_count = query.count()
        
        # Calculate pagination
        offset = (page - 1) * size
        total_pages = (total_count + size - 1) // size
        
        # Get airlines
        airlines = query.offset(offset).limit(size).all()
        
        # Convert to response format
        airline_data = []
        for airline in airlines:
            airline_data.append({
                "airline_code": airline.airline_code,
                "airline_name": airline.airline_name
            })
        
        return {
            "airlines": airline_data,
            "total_count": total_count,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "has_more": page < total_pages
        }
        
    except Exception as e:
        logger.error("Error retrieving airlines", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve airlines"
        )


@router.get(
    "/destinations",
    summary="List destinations", 
    description="Get list of unique destinations for filter dropdown"
)
async def list_destinations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: Optional[str] = Query(None, description="Search destination name"),
    country: Optional[str] = Query(None, description="Filter by country"),
    db: Session = Depends(get_db)
):
    """Get list of unique destinations for filter dropdown"""
    try:
        # Get unique destinations
        query = db.query(Flight.location_en).distinct()
        
        # Apply filters
        if search:
            query = query.filter(Flight.location_en.ilike(f"%{search}%"))
        if country:
            query = query.filter(Flight.location_en.ilike(f"%{country}%"))
        
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


# Add a separate destinations endpoint at the root level
@router.get(
    "/destinations",
    summary="List all destinations",
    description="Get list of all unique destinations for filter dropdown"
)
async def list_all_destinations(
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
