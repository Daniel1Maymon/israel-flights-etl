"""
Destinations endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, text
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
    size: int = Query(20, ge=1, le=50, description="Items per page"),
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


@router.get(
    "/destinations/cities",
    summary="Autocomplete city search",
    description="Search departure destination cities by partial name (EN or HE, case-insensitive)"
)
async def search_cities(
    q: Optional[str] = Query(None, description="Partial city name in English or Hebrew"),
    db: Session = Depends(get_db)
):
    """
    Return one result per city (not per airport).

    Grouping strategy:
    - Rows WITH a Hebrew name are grouped by their first Hebrew word
      (e.g. 'לונדון לוטון' → first word 'לונדון'), so all London-area
      airports collapse into a single 'LONDON / לונדון' entry.
    - Rows WITHOUT a Hebrew name are grouped by location_city_en.

    The canonical English name is MIN(location_city_en) within each group,
    which reliably picks 'LONDON' over 'LONDON LUTON' or 'STANSTED'.
    The canonical Hebrew name is the first Hebrew word used as the group key,
    which is later passed to the performance endpoint so ILIKE '%לונדון%'
    captures every airport whose Hebrew name starts with that word.
    """
    try:
        pattern = f"%{q.strip()}%" if q and q.strip() else "%"

        rows = db.execute(
            text("""
                SELECT
                    MIN(location_city_en) AS city_en,
                    MIN(CASE
                        WHEN location_he IS NOT NULL AND TRIM(location_he) != ''
                            THEN SPLIT_PART(TRIM(location_he), ' ', 1)
                        ELSE NULL
                    END) AS city_he
                FROM flights
                WHERE direction = 'D'
                  AND location_city_en IS NOT NULL
                  AND location_city_en != ''
                  AND (location_city_en ILIKE :pattern OR location_he ILIKE :pattern)
                GROUP BY
                    CASE
                        WHEN location_he IS NOT NULL AND TRIM(location_he) != ''
                            THEN SPLIT_PART(TRIM(location_he), ' ', 1)
                        ELSE location_city_en
                    END
                ORDER BY MIN(location_city_en)
                LIMIT 10
            """),
            {"pattern": pattern},
        ).fetchall()

        cities = [
            {"city_en": row.city_en, "city_he": row.city_he}
            for row in rows
            if row.city_en
        ]

        return {"cities": cities}

    except Exception as e:
        logger.error("Error searching cities", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to search cities")


@router.get(
    "/destinations/airline-performance",
    summary="Airline performance by destination city",
    description="Aggregated departure performance metrics per airline for a given city"
)
async def get_airline_performance(
    city: str = Query(..., description="City name in English (used as fallback)"),
    city_he: Optional[str] = Query(None, description="Canonical Hebrew city word for comprehensive airport matching"),
    min_flights: int = Query(10, ge=1, description="Minimum flights an airline must have to appear (filters out statistically meaningless samples)"),
    db: Session = Depends(get_db)
):
    """
    Returns on-time %, cancellation %, and average delay (delayed flights only)
    grouped by airline for departures to the specified city.

    When city_he is provided the WHERE clause matches location_he ILIKE '%{city_he}%',
    which captures ALL airports for that city (e.g. Heathrow + Luton + Stansted for
    city_he='לונדון').  Falls back to location_city_en ILIKE when city_he is absent.
    """
    try:
        if city_he and city_he.strip():
            where_sql = "location_he ILIKE :pattern AND direction = 'D'"
            params: dict = {"pattern": f"%{city_he.strip()}%"}
        else:
            where_sql = "location_city_en ILIKE :pattern AND direction = 'D'"
            params = {"pattern": f"%{city}%"}

        params["min_flights"] = min_flights

        rows = db.execute(
            text(f"""
                SELECT
                    airline_name,
                    COUNT(*) AS total_flights,
                    ROUND(
                        100.0 * SUM(CASE WHEN delay_minutes <= 15 THEN 1 ELSE 0 END) / COUNT(*),
                        2
                    ) AS on_time_pct,
                    ROUND(
                        100.0 * SUM(CASE WHEN status_en = 'CANCELED' THEN 1 ELSE 0 END) / COUNT(*),
                        2
                    ) AS cancelled_pct,
                    ROUND(
                        AVG(CASE WHEN delay_minutes > 0 THEN delay_minutes END),
                        2
                    ) AS avg_delay_minutes_positive_only
                FROM flights
                WHERE {where_sql}
                GROUP BY airline_name
                HAVING COUNT(*) >= :min_flights
                ORDER BY on_time_pct DESC
            """),
            params,
        ).fetchall()

        airlines = [
            {
                "airline_name": row.airline_name,
                "total_flights": row.total_flights,
                "on_time_pct": float(row.on_time_pct) if row.on_time_pct is not None else 0.0,
                "cancelled_pct": float(row.cancelled_pct) if row.cancelled_pct is not None else 0.0,
                "avg_delay_minutes_positive_only": (
                    float(row.avg_delay_minutes_positive_only)
                    if row.avg_delay_minutes_positive_only is not None
                    else None
                ),
            }
            for row in rows
            if row.airline_name
        ]

        return {"city": city, "airlines": airlines}

    except Exception as e:
        logger.error("Error retrieving airline performance", city=city, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve airline performance")
