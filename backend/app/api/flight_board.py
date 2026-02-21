"""
Flight Board endpoints — SSE stream and filter options for the live board
"""
import asyncio
import json
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import structlog

from app.database import get_db, SessionLocal
from app.models.flight import Flight

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/flight-board", tags=["flight-board"])

REFRESH_INTERVAL = 30  # seconds between DB re-queries on the server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_query(
    db: Session,
    direction: Optional[str],
    flight_number: Optional[str],
    airline_code: Optional[str],
    location: Optional[str],
    terminal: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    sort_by: str,
    sort_order: str,
    page: int,
    size: int,
):
    query = db.query(Flight)

    if direction:
        query = query.filter(Flight.direction == direction)
    if flight_number:
        query = query.filter(Flight.flight_number.ilike(f"%{flight_number}%"))
    if airline_code:
        query = query.filter(Flight.airline_code == airline_code)
    if location:
        query = query.filter(
            or_(
                Flight.location_en.ilike(f"%{location}%"),
                Flight.location_he.ilike(f"%{location}%"),
                Flight.location_city_en.ilike(f"%{location}%"),
            )
        )
    if terminal:
        query = query.filter(Flight.terminal == terminal)
    if date_from:
        query = query.filter(Flight.scheduled_time >= date_from)
    if date_to:
        query = query.filter(Flight.scheduled_time <= date_to)

    sort_map = {
        "scheduled_time": Flight.scheduled_time,
        "actual_time": Flight.actual_time,
        "airline_name": Flight.airline_name,
        "status_en": Flight.status_en,
        "flight_number": Flight.flight_number,
    }
    field = sort_map.get(sort_by, Flight.scheduled_time)
    query = query.order_by(field.desc() if sort_order == "desc" else field.asc())

    total = query.count()
    offset = (page - 1) * size
    rows = query.offset(offset).limit(size).all()
    total_pages = max(1, (total + size - 1) // size)

    return rows, total, total_pages


def _serialize(flight: Flight) -> dict:
    return {
        "flight_id": flight.flight_id,
        "flight_number": flight.flight_number,
        "airline_code": flight.airline_code,
        "airline_name": flight.airline_name,
        "direction": flight.direction,
        "location_iata": flight.location_iata,
        "location_en": flight.location_en,
        "location_he": flight.location_he,
        "location_city_en": flight.location_city_en,
        "country_en": flight.country_en,
        "terminal": flight.terminal,
        "scheduled_time": flight.scheduled_time.isoformat() if flight.scheduled_time else None,
        "actual_time": flight.actual_time.isoformat() if flight.actual_time else None,
        "status_en": flight.status_en,
        "status_he": flight.status_he,
        "delay_minutes": flight.delay_minutes,
    }


# ---------------------------------------------------------------------------
# SSE stream endpoint
# ---------------------------------------------------------------------------

@router.get("/stream", summary="Live flight board SSE stream")
async def stream_flight_board(
    request: Request,
    direction: Optional[str] = Query(None, description="A=Arrivals, D=Departures"),
    flight_number: Optional[str] = Query(None),
    airline_code: Optional[str] = Query(None),
    location: Optional[str] = Query(None, description="City/airport filter"),
    terminal: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sort_by: str = Query("scheduled_time"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """
    Server-Sent Events endpoint for the live flight board.
    Sends the current page of matching flights immediately on connect,
    then re-queries the database every REFRESH_INTERVAL seconds and
    pushes updated data to the client.
    """

    async def event_stream():
        loop = asyncio.get_event_loop()

        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected from flight board")
                break

            try:
                def query_db():
                    db = SessionLocal()
                    try:
                        rows, total, total_pages = _build_query(
                            db=db,
                            direction=direction,
                            flight_number=flight_number,
                            airline_code=airline_code,
                            location=location,
                            terminal=terminal,
                            date_from=date_from,
                            date_to=date_to,
                            sort_by=sort_by,
                            sort_order=sort_order,
                            page=page,
                            size=size,
                        )
                        return [_serialize(r) for r in rows], total, total_pages
                    finally:
                        db.close()

                flight_data, total, total_pages = await loop.run_in_executor(None, query_db)

                payload = json.dumps({
                    "type": "flights",
                    "data": flight_data,
                    "pagination": {
                        "page": page,
                        "size": size,
                        "total": total,
                        "pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                })
                yield f"data: {payload}\n\n"

            except Exception as exc:
                logger.error("SSE stream error", error=str(exc))
                yield f"data: {json.dumps({'type': 'error', 'message': 'Server error, retrying...'})}\n\n"

            await asyncio.sleep(REFRESH_INTERVAL)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Filter options endpoint
# ---------------------------------------------------------------------------

@router.get("/options", summary="Get filter dropdown options")
async def get_filter_options(
    direction: Optional[str] = Query(None, description="A or D to pre-filter options"),
    db: Session = Depends(get_db),
):
    """Return unique airlines, cities, and terminals for populating filter dropdowns."""
    try:
        base = db.query(Flight)
        if direction:
            base = base.filter(Flight.direction == direction)

        airlines_q = (
            base.with_entities(Flight.airline_code, Flight.airline_name)
            .distinct()
            .order_by(Flight.airline_name)
            .all()
        )
        airlines = [
            {"code": a.airline_code, "name": a.airline_name}
            for a in airlines_q
            if a.airline_code and a.airline_name
        ]

        cities_q = (
            base.with_entities(Flight.location_en)
            .distinct()
            .order_by(Flight.location_en)
            .all()
        )
        cities = [c.location_en for c in cities_q if c.location_en]

        terminals_q = (
            base.with_entities(Flight.terminal)
            .distinct()
            .order_by(Flight.terminal)
            .all()
        )
        terminals = [t.terminal for t in terminals_q if t.terminal]

        return {"airlines": airlines, "cities": cities, "terminals": terminals}

    except Exception as exc:
        logger.error("Error fetching filter options", error=str(exc))
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to fetch filter options")
