from datetime import datetime, date
from typing import Optional, List
from sqlalchemy.orm import Query
from sqlalchemy import and_, or_, func

from app.models.flight import Flight


class FlightFilters:
    """Flight filtering and search utilities"""
    
    def __init__(
        self,
        direction: Optional[str] = None,
        airline_code: Optional[str] = None,
        status: Optional[str] = None,
        terminal: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        delay_min: Optional[int] = None,
        delay_max: Optional[int] = None,
        search_query: Optional[str] = None,
        search_fields: Optional[List[str]] = None
    ):
        self.direction = direction
        self.airline_code = airline_code
        self.status = status
        self.terminal = terminal
        self.date_from = date_from
        self.date_to = date_to
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.search_query = search_query
        self.search_fields = search_fields or [
            'airline_name', 'location_en', 'location_he', 
            'location_city_en', 'country_en', 'country_he',
            'flight_number', 'airline_code'
        ]


def build_flight_query(
    query: Query,
    filters: FlightFilters
) -> Query:
    """Build SQLAlchemy query with filters applied"""
    
    # Direction filter
    if filters.direction:
        query = query.filter(Flight.direction == filters.direction)
    
    # Airline code filter
    if filters.airline_code:
        query = query.filter(Flight.airline_code == filters.airline_code)
    
    # Status filter
    if filters.status:
        query = query.filter(Flight.status_en == filters.status)
    
    # Terminal filter
    if filters.terminal:
        query = query.filter(Flight.terminal == filters.terminal)
    
    # Date range filter
    if filters.date_from:
        query = query.filter(Flight.scheduled_time >= filters.date_from)
    
    if filters.date_to:
        # Add one day to include the entire end date
        next_day = datetime.combine(filters.date_to, datetime.min.time())
        query = query.filter(Flight.scheduled_time < next_day)
    
    # Delay filters
    if filters.delay_min is not None:
        query = query.filter(Flight.delay_minutes >= filters.delay_min)
    
    if filters.delay_max is not None:
        query = query.filter(Flight.delay_minutes <= filters.delay_max)
    
    # Search filter
    if filters.search_query:
        search_conditions = []
        for field in filters.search_fields:
            if hasattr(Flight, field):
                search_conditions.append(
                    func.lower(getattr(Flight, field)).contains(
                        filters.search_query.lower()
                    )
                )
        
        if search_conditions:
            query = query.filter(or_(*search_conditions))
    
    return query


def calculate_pagination_info(page: int, size: int, total: int) -> dict:
    """Calculate pagination metadata"""
    pages = (total + size - 1) // size  # Ceiling division
    has_next = page < pages
    has_prev = page > 1
    
    return {
        "page": page,
        "size": size,
        "total": total,
        "pages": pages,
        "has_next": has_next,
        "has_prev": has_prev
    }

