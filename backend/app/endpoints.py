"""
Central endpoints file - All API endpoints in one place
This file contains all endpoint definitions for easy reference and management
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_
import structlog
import time

from app.api.deps import get_database, validate_page_size, validate_page_number
from app.models.flight import Flight
from app.schemas.flight import (
    Flight as FlightSchema,
    FlightListResponse,
    FlightStats,
    AirlineInfo,
    DestinationInfo,
    ErrorResponse
)
from app.utils.filters import FlightFilters, build_flight_query, calculate_pagination_info
from app.config import settings
from app.database import check_db_connection
from app.urls import (
    ROOT_URL, HEALTH_URL, READY_URL, METRICS_URL,
    FLIGHTS_LIST_URL, FLIGHTS_DETAIL_URL, FLIGHTS_SEARCH_URL,
    FLIGHTS_STATS_URL, FLIGHTS_AIRLINES_URL, FLIGHTS_DESTINATIONS_URL,
    FLIGHTS_DELAYS_URL
)

logger = structlog.get_logger()

# Create main router for all endpoints
router = APIRouter()

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@router.get(
    ROOT_URL,
    summary="API Root",
    description="API root endpoint"
)
async def root():
    """API root endpoint"""
    return {
        "message": "Israel Flights API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }


@router.get(
    HEALTH_URL,
    summary="Health check",
    description="Basic health check endpoint"
)
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.api_version
    }


@router.get(
    READY_URL,
    summary="Readiness check",
    description="Check if application is ready to serve traffic"
)
async def readiness_check():
    """Readiness check including database connectivity"""
    try:
        # Check database connection
        if not check_db_connection():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        return {
            "status": "ready",
            "timestamp": time.time(),
            "version": settings.api_version,
            "database": "connected"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )


@router.get(
    METRICS_URL,
    summary="Basic metrics",
    description="Basic application metrics"
)
async def metrics():
    """Basic application metrics"""
    try:
        # Get basic stats
        db_healthy = check_db_connection()
        
        return {
            "timestamp": time.time(),
            "version": settings.api_version,
            "database": "healthy" if db_healthy else "unhealthy",
            "uptime": time.time()  # This would be better with actual uptime tracking
        }
        
    except Exception as e:
        logger.error("Metrics collection failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect metrics"
        )


# ============================================================================
# FLIGHT DATA ENDPOINTS
# ============================================================================

@router.get(
    FLIGHTS_LIST_URL,
    response_model=FlightListResponse,
    summary="List flights",
    description="Retrieve paginated list of flights with optional filtering"
)
async def list_flights(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    sort_by: str = Query("scheduled_time", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order (asc or desc)"),
    direction: Optional[str] = Query(None, description="Filter by direction (A=Arrival, D=Departure)"),
    airline_code: Optional[str] = Query(None, description="Filter by airline code"),
    status: Optional[str] = Query(None, description="Filter by status"),
    terminal: Optional[str] = Query(None, description="Filter by terminal"),
    date_from: Optional[date] = Query(None, description="Filter flights from date"),
    date_to: Optional[date] = Query(None, description="Filter flights to date"),
    delay_min: Optional[int] = Query(None, ge=0, description="Minimum delay in minutes"),
    delay_max: Optional[int] = Query(None, ge=0, description="Maximum delay in minutes"),
    db: Session = Depends(get_database)
):
    """List flights with pagination and filtering"""
    try:
        # Validate pagination parameters
        page = validate_page_number(page)
        size = validate_page_size(size)
        
        # Create filters
        filters = FlightFilters(
            direction=direction,
            airline_code=airline_code,
            status=status,
            terminal=terminal,
            date_from=date_from,
            date_to=date_to,
            delay_min=delay_min,
            delay_max=delay_max
        )
        
        # Build base query
        query = db.query(Flight)
        query = build_flight_query(query, filters)
        
        # Apply sorting
        if hasattr(Flight, sort_by):
            sort_column = getattr(Flight, sort_by)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        else:
            # Default sorting by scheduled_time desc if field doesn't exist
            query = query.order_by(desc(Flight.scheduled_time))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        flights = query.offset(offset).limit(size).all()
        
        # Calculate pagination info
        pagination = calculate_pagination_info(page, size, total)
        
        # Convert to response format
        flight_data = [FlightSchema.model_validate(flight) for flight in flights]
        
        return FlightListResponse(data=flight_data, pagination=pagination)
        
    except Exception as e:
        logger.error("Error listing flights", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve flights"
        )


@router.get(
    FLIGHTS_SEARCH_URL,
    response_model=FlightListResponse,
    summary="Search flights",
    description="Search flights by various criteria"
)
async def search_flights(
    q: str = Query(..., min_length=2, description="Search query"),
    search_fields: Optional[str] = Query(None, description="Comma-separated fields to search in"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    direction: Optional[str] = Query(None, description="Filter by direction"),
    airline_code: Optional[str] = Query(None, description="Filter by airline code"),
    status: Optional[str] = Query(None, description="Filter by status"),
    terminal: Optional[str] = Query(None, description="Filter by terminal"),
    date_from: Optional[date] = Query(None, description="Filter flights from date"),
    date_to: Optional[date] = Query(None, description="Filter flights to date"),
    delay_min: Optional[int] = Query(None, ge=0, description="Minimum delay in minutes"),
    delay_max: Optional[int] = Query(None, ge=0, description="Maximum delay in minutes"),
    db: Session = Depends(get_database)
):
    """Search flights with query and filters"""
    try:
        # Validate pagination parameters
        page = validate_page_number(page)
        size = validate_page_size(size)
        
        # Parse search fields
        search_field_list = None
        if search_fields:
            search_field_list = [field.strip() for field in search_fields.split(",")]
        
        # Create filters
        filters = FlightFilters(
            direction=direction,
            airline_code=airline_code,
            status=status,
            terminal=terminal,
            date_from=date_from,
            date_to=date_to,
            delay_min=delay_min,
            delay_max=delay_max,
            search_query=q,
            search_fields=search_field_list
        )
        
        # Build base query
        query = db.query(Flight)
        query = build_flight_query(query, filters)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        flights = query.offset(offset).limit(size).all()
        
        # Calculate pagination info
        pagination = calculate_pagination_info(page, size, total)
        
        # Convert to response format
        flight_data = [FlightSchema.model_validate(flight) for flight in flights]
        
        return FlightListResponse(data=flight_data, pagination=pagination)
        
    except Exception as e:
        logger.error("Error searching flights", query=q, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search flights"
        )


@router.get(
    FLIGHTS_STATS_URL,
    response_model=FlightStats,
    summary="Get flight statistics",
    description="Get aggregated flight statistics"
)
async def get_flight_stats(
    date_from: Optional[date] = Query(None, description="Start date for statistics"),
    date_to: Optional[date] = Query(None, description="End date for statistics"),
    group_by: Optional[str] = Query(None, description="Group by field (airline, destination, hour, day)"),
    db: Session = Depends(get_database)
):
    """Get flight statistics"""
    try:
        # Base query
        query = db.query(Flight)
        
        # Apply date filters
        if date_from:
            query = query.filter(Flight.scheduled_time >= date_from)
        if date_to:
            next_day = date_to.replace(day=date_to.day + 1) if date_to.day < 28 else date_to.replace(month=date_to.month + 1, day=1)
            query = query.filter(Flight.scheduled_time < next_day)
        
        # Get basic stats
        total_flights = query.count()
        on_time_flights = query.filter(Flight.delay_minutes <= 0).count()
        delayed_flights = query.filter(Flight.delay_minutes > 0).count()
        
        # Calculate average delay
        avg_delay_result = query.filter(Flight.delay_minutes.isnot(None)).with_entities(
            func.avg(Flight.delay_minutes)
        ).scalar()
        average_delay = float(avg_delay_result) if avg_delay_result else 0.0
        
        # Group by specific field if requested
        by_airline = None
        by_destination = None
        by_hour = None
        by_day = None
        
        if group_by == "airline":
            by_airline = query.group_by(Flight.airline_code, Flight.airline_name).with_entities(
                Flight.airline_code,
                Flight.airline_name,
                func.count(Flight.flight_id).label('total_flights'),
                func.avg(Flight.delay_minutes).label('avg_delay')
            ).all()
            by_airline = [
                {
                    "airline_code": row.airline_code,
                    "airline_name": row.airline_name,
                    "total_flights": row.total_flights,
                    "average_delay": float(row.avg_delay) if row.avg_delay else 0.0
                }
                for row in by_airline
            ]
        
        elif group_by == "destination":
            by_destination = query.group_by(
                Flight.location_iata, Flight.location_en, Flight.location_he,
                Flight.location_city_en, Flight.country_en, Flight.country_he
            ).with_entities(
                Flight.location_iata,
                Flight.location_en,
                Flight.location_he,
                Flight.location_city_en,
                Flight.country_en,
                Flight.country_he,
                func.count(Flight.flight_id).label('total_flights')
            ).all()
            by_destination = [
                {
                    "location_iata": row.location_iata,
                    "location_en": row.location_en,
                    "location_he": row.location_he,
                    "location_city_en": row.location_city_en,
                    "country_en": row.country_en,
                    "country_he": row.country_he,
                    "total_flights": row.total_flights
                }
                for row in by_destination
            ]
        
        return FlightStats(
            total_flights=total_flights,
            on_time_flights=on_time_flights,
            delayed_flights=delayed_flights,
            average_delay=average_delay,
            by_airline=by_airline,
            by_destination=by_destination,
            by_hour=by_hour,
            by_day=by_day
        )
        
    except Exception as e:
        logger.error("Error getting flight stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve flight statistics"
        )


@router.get(
    FLIGHTS_AIRLINES_URL,
    response_model=List[AirlineInfo],
    summary="List airlines",
    description="Get list of unique airlines"
)
async def list_airlines(
    search: Optional[str] = Query(None, description="Search airline names"),
    db: Session = Depends(get_database)
):
    """Get list of unique airlines"""
    try:
        query = db.query(
            Flight.airline_code,
            Flight.airline_name,
            func.count(Flight.flight_id).label('flight_count')
        ).group_by(Flight.airline_code, Flight.airline_name)
        
        if search:
            query = query.filter(
                func.lower(Flight.airline_name).contains(search.lower())
            )
        
        airlines = query.all()
        
        return [
            AirlineInfo(
                airline_code=row.airline_code,
                airline_name=row.airline_name,
                flight_count=row.flight_count
            )
            for row in airlines
        ]
        
    except Exception as e:
        logger.error("Error listing airlines", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve airlines"
        )


@router.get(
    FLIGHTS_DESTINATIONS_URL,
    response_model=List[DestinationInfo],
    summary="List destinations",
    description="Get list of unique destinations"
)
async def list_destinations(
    search: Optional[str] = Query(None, description="Search destination names"),
    country: Optional[str] = Query(None, description="Filter by country"),
    db: Session = Depends(get_database)
):
    """Get list of unique destinations"""
    try:
        query = db.query(
            Flight.location_iata,
            Flight.location_en,
            Flight.location_he,
            Flight.location_city_en,
            Flight.country_en,
            Flight.country_he,
            func.count(Flight.flight_id).label('flight_count')
        ).group_by(
            Flight.location_iata,
            Flight.location_en,
            Flight.location_he,
            Flight.location_city_en,
            Flight.country_en,
            Flight.country_he
        )
        
        if search:
            query = query.filter(
                or_(
                    func.lower(Flight.location_en).contains(search.lower()),
                    func.lower(Flight.location_he).contains(search.lower()),
                    func.lower(Flight.location_city_en).contains(search.lower())
                )
            )
        
        if country:
            query = query.filter(
                func.lower(Flight.country_en).contains(country.lower())
            )
        
        destinations = query.all()
        
        return [
            DestinationInfo(
                location_iata=row.location_iata,
                location_en=row.location_en,
                location_he=row.location_he,
                location_city_en=row.location_city_en,
                country_en=row.country_en,
                country_he=row.country_he,
                flight_count=row.flight_count
            )
            for row in destinations
        ]
        
    except Exception as e:
        logger.error("Error listing destinations", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve destinations"
        )


@router.get(
    FLIGHTS_DETAIL_URL,
    response_model=FlightSchema,
    summary="Get flight by ID",
    description="Retrieve a specific flight by its ID"
)
async def get_flight(
    flight_id: str,
    db: Session = Depends(get_database)
):
    """Get a specific flight by ID"""
    try:
        flight = db.query(Flight).filter(Flight.flight_id == flight_id).first()
        
        if not flight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flight with ID {flight_id} not found"
            )
        
        return FlightSchema.model_validate(flight)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting flight", flight_id=flight_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve flight"
        )


@router.get(
    FLIGHTS_DELAYS_URL,
    summary="Get delayed flights",
    description="Get list of flights with delays"
)
async def get_delayed_flights(
    db: Session = Depends(get_database)
):
    """Get flights with delays - example new endpoint"""
    try:
        # Example implementation
        delayed_flights = db.query(Flight).filter(Flight.delay_minutes > 0).limit(10).all()
        
        return {
            "message": "Delayed flights endpoint",
            "count": len(delayed_flights),
            "flights": [{"flight_id": f.flight_id, "delay": f.delay_minutes} for f in delayed_flights]
        }
        
    except Exception as e:
        logger.error("Error getting delayed flights", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve delayed flights"
        )


# ============================================================================
# ENDPOINT SUMMARY
# ============================================================================
"""
ALL ENDPOINTS IN THIS FILE:

HEALTH & STATUS:
- GET /                    - API root information
- GET /health             - Basic health check
- GET /ready              - Database readiness check
- GET /metrics            - Basic performance metrics

FLIGHT DATA:
- GET /api/v1/flights/           - List flights with pagination/filtering
- GET /api/v1/flights/{id}       - Get specific flight by ID
- GET /api/v1/flights/search     - Search flights by query
- GET /api/v1/flights/stats      - Get flight statistics
- GET /api/v1/flights/airlines   - List unique airlines
- GET /api/v1/flights/destinations - List unique destinations

TOTAL: 10 endpoints
"""
