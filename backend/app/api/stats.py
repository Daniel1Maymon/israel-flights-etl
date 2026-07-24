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
    Return live counts computed from the database on each request, so they
    reflect the latest ETL updates.

    Flight counts:
    - departures: rows with direction = 'D'
    - arrivals:   rows with direction = 'A'
    - flights:    all rows (total in the system)

    Airlines / destinations are scoped to departures (the dashboard's focus):
    - airlines:     distinct airlines operating departures
    - destinations: distinct departure destination cities

    'flights' stays as the departures count for backwards compatibility with the
    original bar; 'departures' is its explicit alias.
    """
    try:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE direction = 'D') AS departures,
                    COUNT(*) FILTER (WHERE direction = 'A') AS arrivals,
                    COUNT(*) AS total,
                    COUNT(DISTINCT airline_name) FILTER (
                        WHERE direction = 'D' AND airline_name IS NOT NULL AND TRIM(airline_name) != ''
                    ) AS airlines,
                    COUNT(DISTINCT location_city_en) FILTER (
                        WHERE direction = 'D' AND location_city_en IS NOT NULL AND TRIM(location_city_en) != ''
                    ) AS destinations
                FROM flights
            """)
        ).fetchone()

        return {
            "departures": int(row.departures or 0),
            "arrivals": int(row.arrivals or 0),
            "total": int(row.total or 0),
            "flights": int(row.departures or 0),  # backwards-compat alias
            "airlines": int(row.airlines or 0),
            "destinations": int(row.destinations or 0),
        }

    except Exception as e:
        logger.error("Error retrieving stats overview", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve stats overview")
