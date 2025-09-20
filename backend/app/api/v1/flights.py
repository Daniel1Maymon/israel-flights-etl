from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_
import structlog

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

logger = structlog.get_logger()
router = APIRouter()


@router.get(
    "/",
    response_model=FlightListResponse,
    summary="List flights",
    description="Retrieve paginated list of flights with optional filtering"
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
    "/{flight_id}",
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
    "/search",
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
    "/stats",
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
    "/airlines",
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
    "/destinations",
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
