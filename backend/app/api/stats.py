"""
Overview statistics endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

from app.database import get_db

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["stats"])


@router.get(
    "/stats/overview",
    summary="Departure overview counts",
    description="Total departure flights, distinct airlines, and distinct destination cities",
)
async def get_stats_overview(db: Session = Depends(get_db)):
    """
    Return live counts for departure flights only (direction = 'D'):
    - flights: total departure flight rows
    - airlines: distinct airlines operating departures
    - destinations: distinct destination cities

    Values are computed from the database on each request, so they reflect
    the latest ETL updates.
    """
    try:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*) AS flights,
                    COUNT(DISTINCT airline_name) FILTER (
                        WHERE airline_name IS NOT NULL AND TRIM(airline_name) != ''
                    ) AS airlines,
                    COUNT(DISTINCT location_city_en) FILTER (
                        WHERE location_city_en IS NOT NULL AND TRIM(location_city_en) != ''
                    ) AS destinations
                FROM flights
                WHERE direction = 'D'
            """)
        ).fetchone()

        return {
            "flights": int(row.flights or 0),
            "airlines": int(row.airlines or 0),
            "destinations": int(row.destinations or 0),
        }

    except Exception as e:
        logger.error("Error retrieving stats overview", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve stats overview")
