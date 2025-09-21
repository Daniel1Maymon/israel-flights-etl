"""
Central endpoints file - All API endpoints in one place
This file contains all endpoint definitions for easy reference and management
"""

from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_, case
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

# ============================================================================
# AIRLINE STATISTICS ENDPOINT
# ============================================================================

# Define the response structure for airline statistics
class AirlineStat(BaseModel):
    """Single airline performance data"""
    airline_code: str
    airline_name: str
    total_flights: int
    on_time_flights: int
    on_time_percentage: float
    avg_delay_minutes: float
    cancellation_percentage: float

class AirlineStatsResponse(BaseModel):
    """Response containing all airline statistics"""
    airlines: List[AirlineStat]
    total_airlines: int
    retrieved_at: float

@router.get(
    "/api/v1/airlines/stats",
    response_model=AirlineStatsResponse,
    summary="Get airline performance statistics",
    description="Get on-time performance statistics for all airlines"
)
async def get_airline_stats(
    destination: Optional[str] = Query(None, description="Filter by destination country"),
    date_range: Optional[str] = Query(None, description="Filter by date range (last-7-days, last-30-days, last-90-days, last-6-months, last-year)"),
    day_of_week: Optional[str] = Query(None, description="Filter by day of week (monday, tuesday, wednesday, thursday, friday, saturday, sunday)"),
    db: Session = Depends(get_database)
) -> AirlineStatsResponse:
    """
    Get airline performance statistics
    
    This endpoint calculates on-time performance for each airline by:
    1. Grouping flights by airline
    2. Counting total flights (excluding NULL delay data)
    3. Counting on-time flights (delay <= 15 minutes)
    4. Calculating on-time percentage
    """
    try:
        # Calculate airline on-time performance statistics
        # This query groups flights by airline and calculates:
        # 1. Total number of flights per airline (excluding NULL delay data)
        # 2. Number of on-time flights (delay <= 15 minutes)
        # 3. On-time percentage (on-time flights / total flights * 100)
        # 4. Results are ordered by best performing airlines first
        
        # Type: SQLAlchemy Query object that will return rows with airline data
        query = db.query(
            # SELECT fields - airline information
            Flight.airline_code,
            Flight.airline_name,
            
            # COUNT(*) becomes func.count(Flight.flight_id)
            func.count(Flight.flight_id).label('total_flights'),
            
            # COUNT(CASE WHEN delay_minutes <= 15 THEN 1 END) becomes:
            func.count(
                case(
                    (Flight.delay_minutes <= 15, 1),
                    else_=None
                )
            ).label('on_time_flights'),
            
            # AVG(delay_minutes) for average delay calculation
            func.avg(Flight.delay_minutes).label('avg_delay_minutes'),
            
            # COUNT(CASE WHEN status_en LIKE '%CANCELED%' THEN 1 END) for cancellations
            func.count(
                case(
                    (Flight.status_en.ilike('%canceled%'), 1),
                    else_=None
                )
            ).label('cancelled_flights')
        ).filter(
            # WHERE delay_minutes IS NOT NULL
            Flight.delay_minutes.isnot(None)
        )
        
        # Add destination filter if specified
        if destination and destination != "All":
            query = query.filter(Flight.country_en == destination)
        
        # Add date range filter if specified
        if date_range and date_range != "all-time":
            from datetime import datetime, timedelta
            now = datetime.now()
            
            if date_range == "last-7-days":
                start_date = now - timedelta(days=7)
            elif date_range == "last-30-days":
                start_date = now - timedelta(days=30)
            elif date_range == "last-90-days":
                start_date = now - timedelta(days=90)
            elif date_range == "last-6-months":
                start_date = now - timedelta(days=180)
            elif date_range == "last-year":
                start_date = now - timedelta(days=365)
            else:
                start_date = None
                
            if start_date:
                query = query.filter(Flight.scheduled_time >= start_date)
        
        # Add day of week filter if specified
        if day_of_week and day_of_week != "all-days":
            # Map day names to weekday numbers (Monday=0, Sunday=6)
            day_mapping = {
                'monday': 0,
                'tuesday': 1,
                'wednesday': 2,
                'thursday': 3,
                'friday': 4,
                'saturday': 5,
                'sunday': 6
            }
            
            if day_of_week in day_mapping:
                weekday_num = day_mapping[day_of_week]
                # Use PostgreSQL's EXTRACT function to get day of week
                query = query.filter(func.extract('dow', Flight.scheduled_time) == weekday_num)
        
        query = query.group_by(
            # GROUP BY airline_code, airline_name
            Flight.airline_code,
            Flight.airline_name
        )
        
        # Execute the query
        # Type: List of SQLAlchemy Row objects, each containing airline data
        results: List[Any] = query.all()
        
        # Convert results to a list of AirlineStat objects
        # Type: List[AirlineStat] - each item represents one airline's performance
        airline_stats: List[AirlineStat] = []
        
        for row in results:
            # Calculate metrics in Python
            total_flights = int(row.total_flights)
            on_time_flights = int(row.on_time_flights)
            cancelled_flights = int(row.cancelled_flights)
            
            # Calculate percentages
            on_time_percentage = (on_time_flights / total_flights * 100) if total_flights > 0 else 0.0
            cancellation_percentage = (cancelled_flights / total_flights * 100) if total_flights > 0 else 0.0
            
            # Calculate average delay (handle NULL values)
            avg_delay_minutes = float(row.avg_delay_minutes) if row.avg_delay_minutes is not None else 0.0
            
            # Type: AirlineStat - single airline performance data
            airline_stat: AirlineStat = AirlineStat(
                airline_code=str(row.airline_code),
                airline_name=str(row.airline_name),
                total_flights=total_flights,
                on_time_flights=on_time_flights,
                on_time_percentage=round(on_time_percentage, 2),
                avg_delay_minutes=round(avg_delay_minutes, 1),
                cancellation_percentage=round(cancellation_percentage, 2)
            )
            airline_stats.append(airline_stat)
        
        # Filter out airlines with too few flights for reliable statistics
        # Minimum 10 flights required for meaningful analysis
        MIN_FLIGHTS_THRESHOLD = 10
        airline_stats = [airline for airline in airline_stats if airline.total_flights >= MIN_FLIGHTS_THRESHOLD]
        
        # Sort by on-time percentage (best first)
        airline_stats.sort(key=lambda x: x.on_time_percentage, reverse=True)
        
        logger.info("Airline stats retrieved successfully", count=len(airline_stats))
        
        # Type: AirlineStatsResponse - the complete response structure
        response: AirlineStatsResponse = AirlineStatsResponse(
            airlines=airline_stats,
            total_airlines=len(airline_stats),
            retrieved_at=time.time()
        )
        
        return response
        
    except Exception as e:
        logger.error("Error retrieving airline stats", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve airline statistics"
        )


class DestinationResponse(BaseModel):
    """Response containing all available destinations"""
    countries: List[str]
    total_countries: int
    retrieved_at: float

@router.get(
    "/api/v1/destinations",
    response_model=DestinationResponse,
    summary="Get all available destinations",
    description="Get list of all countries from the flight data"
)
async def get_destinations(db: Session = Depends(get_database)) -> DestinationResponse:
    """
    Get all available destinations (countries) from the flight data
    
    This endpoint retrieves all unique countries from the flights table
    to populate the destination filter dropdown in the frontend.
    """
    try:
        query = db.query(
            func.distinct(Flight.country_en).label('country')
        ).filter(
            Flight.country_en.isnot(None),
            Flight.country_en != ''
        ).order_by(
            Flight.country_en
        )
        
        results: List[Any] = query.all()
        countries: List[str] = [str(row.country) for row in results if row.country]
        
        logger.info("Destinations retrieved successfully", count=len(countries))
        
        response: DestinationResponse = DestinationResponse(
            countries=countries,
            total_countries=len(countries),
            retrieved_at=time.time()
        )
        
        return response
        
    except Exception as e:
        logger.error("Failed to retrieve destinations", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve destinations"
        )

