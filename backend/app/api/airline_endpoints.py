"""
Airline Statistics API Endpoints

This module provides REST API endpoints for accessing airline performance data.
It uses the AirlineAggregationService to calculate KPIs from raw flight data.

Key Concepts for Junior Data Engineers:
1. API Endpoints: URLs that clients can call to get data
2. Dependency Injection: Passing services to endpoints
3. Error Handling: Managing failures gracefully
4. Response Serialization: Converting data to JSON format
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, case
from sqlalchemy.orm import Session
import structlog

from app.api.deps import get_database
from app.models.flight import Flight
from app.services.airline_aggregation import AirlineAggregationService
from app.schemas.airline import (
    AirlineStatsResponse,
    AirlineTopBottomResponse,
    AirlineFilterParams
)

logger = structlog.get_logger()

# Create router for airline endpoints
router = APIRouter(prefix="/api/v1/airlines", tags=["airlines"])


@router.get(
    "/stats",
    response_model=AirlineStatsResponse,
    summary="Get airline statistics",
    description="Get comprehensive airline performance statistics aggregated from flight data"
)
async def get_airline_stats(
    # Date range filters
    date_from: Optional[datetime] = Query(None, description="Start date for filtering flights (ISO format)"),
    date_to: Optional[datetime] = Query(None, description="End date for filtering flights (ISO format)"),
    
    # Destination filters
    destination: Optional[str] = Query(None, description="Filter by destination name"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    
    # Airline filters
    airline_codes: Optional[str] = Query(None, description="Comma-separated list of airline codes to include"),
    
    # Performance filters
    min_flights: int = Query(1, ge=1, description="Minimum number of flights required for inclusion"),
    min_on_time_percentage: Optional[float] = Query(None, ge=0, le=100, description="Minimum on-time percentage"),
    max_avg_delay: Optional[float] = Query(None, ge=0, description="Maximum average delay in minutes"),
    
    # Sorting and pagination
    sort_by: str = Query("on_time_percentage", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    limit: Optional[int] = Query(50, ge=1, le=100, description="Maximum number of airlines to return (max 100)"),
    
    # Database dependency
    db: Session = Depends(get_database)
):
    """
    Get comprehensive airline performance statistics
    
    This endpoint aggregates individual flight records into airline-level KPIs.
    It's the main endpoint for getting airline performance data.
    
    Example usage:
    - GET /api/v1/airlines/stats - Get all airline stats
    - GET /api/v1/airlines/stats?min_flights=100 - Only airlines with 100+ flights
    - GET /api/v1/airlines/stats?destination=New York - Only flights to New York
    - GET /api/v1/airlines/stats?sort_by=total_flights&sort_order=desc - Sort by flight count
    """
    try:
        # Parse airline codes if provided
        airline_codes_list = None
        if airline_codes:
            airline_codes_list = [code.strip().upper() for code in airline_codes.split(",")]
        
        # Create filter parameters
        filters = AirlineFilterParams(
            date_from=date_from,
            date_to=date_to,
            destination=destination,
            country=country,
            airline_codes=airline_codes_list,
            min_flights=min_flights,
            min_on_time_percentage=min_on_time_percentage,
            max_avg_delay=max_avg_delay,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit
        )
        
        # Create aggregation service and calculate KPIs
        aggregation_service = AirlineAggregationService(db)
        result = aggregation_service.calculate_airline_kpis(filters)
        
        logger.info(
            "Airline stats retrieved successfully",
            airlines_count=result.total_airlines,
            total_flights=result.total_flights,
            calculation_time_ms=result.calculation_time_ms
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving airline stats", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve airline statistics"
        )


@router.get(
    "/top-bottom",
    response_model=AirlineTopBottomResponse,
    summary="Get top and bottom performing airlines",
    description="Get the best and worst performing airlines based on on-time percentage"
)
async def get_top_bottom_airlines(
    # Date range filters
    date_from: Optional[datetime] = Query(None, description="Start date for filtering flights"),
    date_to: Optional[datetime] = Query(None, description="End date for filtering flights"),
    
    # Destination filters
    destination: Optional[str] = Query(None, description="Filter by destination name"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    
    # Airline filters
    airline_codes: Optional[str] = Query(None, description="Comma-separated list of airline codes"),
    
    # Performance filters
    min_flights: int = Query(1, ge=1, description="Minimum number of flights required"),
    min_on_time_percentage: Optional[float] = Query(None, ge=0, le=100, description="Minimum on-time percentage"),
    max_avg_delay: Optional[float] = Query(None, ge=0, description="Maximum average delay"),
    
    # Top/bottom limits
    top_limit: int = Query(5, ge=1, le=20, description="Number of top airlines to return (max 20)"),
    bottom_limit: int = Query(5, ge=1, le=20, description="Number of bottom airlines to return (max 20)"),
    
    # Database dependency
    db: Session = Depends(get_database)
):
    """
    Get top and bottom performing airlines
    
    This endpoint is useful for creating leaderboards and identifying
    airlines that need improvement. It returns the best and worst
    performing airlines based on on-time percentage.
    
    Example usage:
    - GET /api/v1/airlines/top-bottom - Get top 5 and bottom 5
    - GET /api/v1/airlines/top-bottom?top_limit=10&bottom_limit=10 - Get top 10 and bottom 10
    - GET /api/v1/airlines/top-bottom?min_flights=50 - Only airlines with 50+ flights
    """
    try:
        # Parse airline codes if provided
        airline_codes_list = None
        if airline_codes:
            airline_codes_list = [code.strip().upper() for code in airline_codes.split(",")]
        
        # Create filter parameters
        filters = AirlineFilterParams(
            date_from=date_from,
            date_to=date_to,
            destination=destination,
            country=country,
            airline_codes=airline_codes_list,
            min_flights=min_flights,
            min_on_time_percentage=min_on_time_percentage,
            max_avg_delay=max_avg_delay,
            sort_by="on_time_percentage",  # Always sort by on-time percentage for top/bottom
            sort_order="desc"
        )
        
        # Create aggregation service and get top/bottom airlines
        aggregation_service = AirlineAggregationService(db)
        result = aggregation_service.get_top_bottom_airlines(
            filters=filters,
            top_limit=top_limit,
            bottom_limit=bottom_limit
        )
        
        logger.info(
            "Top/bottom airlines retrieved successfully",
            top_count=len(result.top_airlines),
            bottom_count=len(result.bottom_airlines),
            total_airlines=result.total_airlines
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving top/bottom airlines", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve top/bottom airlines"
        )


@router.get(
    "/destinations",
    summary="Get unique destinations",
    description="Get list of unique destinations served by airlines with pagination"
)
async def get_airline_destinations(
    # Date range filters
    date_from: Optional[datetime] = Query(None, description="Start date for filtering flights"),
    date_to: Optional[datetime] = Query(None, description="End date for filtering flights"),
    
    # Search filters
    search: Optional[str] = Query(None, description="Search destination names"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    
    # Database dependency
    db: Session = Depends(get_database)
):
    """
    Get unique destinations served by airlines with pagination
    
    This endpoint returns a paginated list of unique destinations that appear
    in the flight data, which is useful for populating dropdown filters.
    
    Example usage:
    - GET /api/v1/airlines/destinations - Get first 50 destinations
    - GET /api/v1/airlines/destinations?search=New York - Search for destinations containing "New York"
    - GET /api/v1/airlines/destinations?country=United States - Only US destinations
    - GET /api/v1/airlines/destinations?page=2&size=100 - Get page 2 with 100 items
    """
    try:
        from app.models.flight import Flight
        from sqlalchemy import func, or_, distinct
        from app.api.deps import validate_page_number, validate_page_size
        
        # Validate pagination parameters
        page = validate_page_number(page)
        size = validate_page_size(size)
        
        # Build base query
        query = db.query(
            Flight.location_en,
            Flight.location_he,
            Flight.location_city_en,
            Flight.country_en,
            Flight.country_he,
            func.count(Flight.flight_id).label('flight_count')
        ).group_by(
            Flight.location_en,
            Flight.location_he,
            Flight.location_city_en,
            Flight.country_en,
            Flight.country_he
        )
        
        # Apply date filters
        if date_from:
            query = query.filter(Flight.scheduled_time >= date_from)
        if date_to:
            query = query.filter(Flight.scheduled_time <= date_to)
        
        # Apply search filter
        if search:
            query = query.filter(
                or_(
                    Flight.location_en.ilike(f"%{search}%"),
                    Flight.location_he.ilike(f"%{search}%"),
                    Flight.location_city_en.ilike(f"%{search}%")
                )
            )
        
        # Apply country filter
        if country:
            query = query.filter(
                or_(
                    Flight.country_en.ilike(f"%{country}%"),
                    Flight.country_he.ilike(f"%{country}%")
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        results = query.offset(offset).limit(size).all()
        
        # Format results
        destinations = []
        for row in results:
            destinations.append({
                "location_en": row.location_en,
                "location_he": row.location_he,
                "location_city_en": row.location_city_en,
                "country_en": row.country_en,
                "country_he": row.country_he,
                "flight_count": row.flight_count
            })
        
        logger.info("Destinations retrieved successfully", count=len(destinations), total=total)
        
        return {
            "destinations": destinations,
            "total_destinations": total,
            "page": page,
            "size": size,
            "has_more": (page * size) < total,
            "retrieved_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error("Error retrieving destinations", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve destinations"
        )


@router.get(
    "/health",
    summary="Airline service health check",
    description="Check if the airline aggregation service is working properly"
)
async def airline_service_health(db: Session = Depends(get_database)):
    """
    Health check for the airline aggregation service
    
    This endpoint performs a quick test to ensure the service is working
    and can access the database properly.
    """
    try:
        # Test database connection
        from app.models.flight import Flight
        flight_count = db.query(Flight).count()
        
        # Test aggregation service
        aggregation_service = AirlineAggregationService(db)
        
        # Quick test with minimal data
        test_filters = AirlineFilterParams(min_flights=1, limit=1)
        test_result = aggregation_service.calculate_airline_kpis(test_filters)
        
        return {
            "status": "healthy",
            "database_connected": True,
            "total_flights": flight_count,
            "airlines_available": test_result.total_airlines,
            "checked_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error("Airline service health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Airline service is not healthy"
        )


@router.get(
    "/{airline_code}/destinations",
    summary="Get destinations for specific airline",
    description="Get list of destinations served by a specific airline"
)
async def get_airline_specific_destinations(
    airline_code: str,
    # Date range filters
    date_from: Optional[datetime] = Query(None, description="Start date for filtering flights"),
    date_to: Optional[datetime] = Query(None, description="End date for filtering flights"),
    
    # Search filters
    search: Optional[str] = Query(None, description="Search destination names"),
    lang: str = Query("en", description="Destination language (en or he)"),
    
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    
    # Database dependency
    db: Session = Depends(get_database)
):
    """
    Get destinations served by a specific airline
    
    This endpoint returns destinations that the specified airline flies to,
    which is useful for showing airline-specific destination data.
    """
    try:
        # Build base query for the specific airline
        base_query = db.query(Flight).filter(Flight.airline_code == airline_code.upper())
        
        # Apply date filters
        if date_from:
            base_query = base_query.filter(Flight.scheduled_time >= date_from)
        if date_to:
            base_query = base_query.filter(Flight.scheduled_time <= date_to)
        
        destination_field = Flight.country_he if lang.lower().startswith("he") else Flight.location_city_en

        # Apply search filter
        if search:
            base_query = base_query.filter(destination_field.ilike(f"%{search}%"))

        # Build aggregated query per destination
        query = base_query.with_entities(
            destination_field.label("destination"),
            func.count().label("flights_count"),
            func.round(100.0 * func.avg(
                case(
                    (Flight.delay_minutes.between(0, 20), 1),
                    else_=0
                )
            )).label("on_time_percentage"),
            func.round(func.avg(Flight.delay_minutes)).label("avg_delay_minutes"),
            func.round(100.0 * func.avg(
                case(
                    (Flight.status_en == "CANCELED", 1),
                    else_=0
                )
            )).label("cancel_percentage")
        ).group_by(destination_field).order_by(func.count().desc())

        # Get total count of destination groups
        count_query = db.query(func.count()).select_from(
            base_query.with_entities(destination_field).distinct().subquery()
        )
        total_count = count_query.scalar() or 0
        
        # Calculate pagination
        offset = (page - 1) * size
        total_pages = (total_count + size - 1) // size if total_count else 0
        
        # Get destinations
        destinations = query.offset(offset).limit(size).all()
        
        # Convert to response format
        destination_data = []
        for row in destinations:
            destination_data.append({
                "destination": row.destination,
                "airline_code": airline_code.upper(),
                "total_flights": int(row.flights_count or 0),
                "on_time_percentage": int(row.on_time_percentage or 0),
                "avg_delay_minutes": int(row.avg_delay_minutes or 0),
                "cancellation_percentage": int(row.cancel_percentage or 0)
            })
        
        return {
            "destinations": destination_data,
            "airline_code": airline_code.upper(),
            "total_count": total_count,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "has_more": page < total_pages
        }
        
    except Exception as e:
        logger.error("Error retrieving airline destinations", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve airline destinations"
        )


@router.get(
    "/destinations",
    summary="Get all destinations",
    description="Get list of all unique destinations for filter dropdown"
)
async def get_all_destinations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: Optional[str] = Query(None, description="Search destination name"),
    db: Session = Depends(get_database)
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
