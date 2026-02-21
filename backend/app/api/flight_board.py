"""
Flight Board endpoints — SSE stream and filter options for the live board.

Default board behaviour (no date filters supplied):
  • "Today" is computed in Asia/Jerusalem (Israel Standard / Daylight time).
  • Only flights whose scheduled_time falls on today's Israel date are shown.
  • The earliest visible flight is 1 hour before the current Israel time
    (so recently-departed / recently-arrived flights stay visible briefly).

When the user supplies date_from / date_to those are treated as Israel-timezone
day boundaries and fully replace the default window.
"""
import asyncio
import json
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import structlog

from app.database import get_db, SessionLocal
from app.models.flight import Flight

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/flight-board", tags=["flight-board"])

REFRESH_INTERVAL = 30  # seconds between DB re-queries on an open SSE connection
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_date_window(
    date_from: Optional[date],
    date_to: Optional[date],
    now_il: Optional[datetime] = None,  # injectable so tests don't need to mock time
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Return (from_dt, to_dt) as timezone-aware datetimes in Asia/Jerusalem.

    No explicit dates supplied (default board view):
        from_dt = now_il - 1 hour          (1-hour-back cutoff)
        to_dt   = end of today in Israel   (23:59:59.999999)

    Explicit dates override the default completely.
    Either or both can be None independently.
    """
    if date_from is None and date_to is None:
        if now_il is None:
            now_il = datetime.now(tz=ISRAEL_TZ)
        from_dt = now_il - timedelta(hours=1)
        to_dt = now_il.replace(hour=23, minute=59, second=59, microsecond=999999)
        return from_dt, to_dt

    from_dt = (
        datetime(date_from.year, date_from.month, date_from.day,
                 0, 0, 0, tzinfo=ISRAEL_TZ)
        if date_from else None
    )
    to_dt = (
        datetime(date_to.year, date_to.month, date_to.day,
                 23, 59, 59, 999999, tzinfo=ISRAEL_TZ)
        if date_to else None
    )
    return from_dt, to_dt


def _build_query(
    db: Session,
    direction: Optional[str],
    flight_number: Optional[str],
    airline_code: Optional[str],
    location: Optional[str],
    terminal: Optional[str],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
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
    if from_dt:
        query = query.filter(Flight.scheduled_time >= from_dt)
    if to_dt:
        query = query.filter(Flight.scheduled_time <= to_dt)

    sort_map = {
        "scheduled_time": Flight.scheduled_time,
        "actual_time": Flight.actual_time,
        "airline_name": Flight.airline_name,
        "status_en": Flight.status_en,
        "flight_number": Flight.flight_number,
    }
    primary = sort_map.get(sort_by, Flight.scheduled_time)
    order_fn = primary.desc() if sort_order == "desc" else primary.asc()
    # Stable secondary sort guarantees consistent page ordering
    query = query.order_by(order_fn, Flight.flight_number.asc())

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
    location: Optional[str] = Query(None, description="City/airport partial-match filter"),
    terminal: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None, description="Start date (Israel timezone)"),
    date_to: Optional[date] = Query(None, description="End date (Israel timezone)"),
    sort_by: str = Query("scheduled_time"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """
    Server-Sent Events stream for the live flight board.

    • On connect: immediately sends current matching flights.
    • Every REFRESH_INTERVAL seconds: re-queries the DB and pushes an update.
    • The Israel-time window is re-evaluated on every refresh so the
      1-hour cutoff slides forward correctly as time passes.
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
                        # Re-compute on every iteration so the cutoff advances with real time
                        from_dt, to_dt = _compute_date_window(date_from, date_to)
                        rows, total, total_pages = _build_query(
                            db=db,
                            direction=direction,
                            flight_number=flight_number,
                            airline_code=airline_code,
                            location=location,
                            terminal=terminal,
                            from_dt=from_dt,
                            to_dt=to_dt,
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
                    "timestamp": datetime.now(tz=ISRAEL_TZ).isoformat(),
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
