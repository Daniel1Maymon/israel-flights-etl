"""
Flight Board endpoints — SSE stream and filter options for the live board.

Default board behaviour (no date filters supplied):
  • "windowStart" = now in Asia/Jerusalem − 60 minutes.
  • "windowEnd"   = the latest scheduled_time across all flights in the DB.

This gives a rolling, self-updating view of live activity: old flights drop off
the back once they are more than 60 minutes past, and the ceiling advances as
the ETL ingests fresher data.

When the user supplies date_from / date_to those are treated as Israel-timezone
day boundaries and fully replace the default window.
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import structlog

from app.config import settings
from app.database import get_db, SessionLocal
from app.models.flight import Flight

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/flight-board", tags=["flight-board"])

REFRESH_INTERVAL = 900   # seconds — board re-queries DB every 15 minutes
HEARTBEAT_INTERVAL = 10  # seconds between SSE keepalive comments (keep connection alive)
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# Hard ceiling on rows leaving this endpoint, regardless of filters or date range.
MAX_BOARD_ROWS = settings.max_public_rows
# Widest span the board will query. Bounds the pre-LIMIT scan; the row cap alone
# does not, because Postgres must still sort the full match set before discarding.
MAX_WINDOW_DAYS = settings.max_board_window_days

# SSE connections are long-lived, so a per-minute rate limit cannot bound how many
# exist at once. A semaphore can.
_sse_slots = asyncio.Semaphore(settings.max_sse_connections)
# Dedicated pool: with the default executor, board queries share the threads serving
# every other endpoint, so a board overload would take the whole app down with it.
_board_executor = ThreadPoolExecutor(
    max_workers=settings.sse_query_threads, thread_name_prefix="board-query"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_latest_window_end(db: Session) -> Optional[datetime]:
    """
    Return the latest scheduled_time across all flights in the DB.
    This becomes the upper bound of the rolling window for the default board view.
    Returns None if the table is empty.
    """
    result = (
        db.query(Flight.scheduled_time)
        .order_by(Flight.scheduled_time.desc())
        .first()
    )
    return result.scheduled_time if result else None


def _compute_date_window(
    date_from: Optional[date],
    date_to: Optional[date],
    now_il: Optional[datetime] = None,   # injectable so tests don't need to mock time
    window_end_dt: Optional[datetime] = None,  # scheduled_time of most-recently-updated flight
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Return (from_dt, to_dt) as timezone-aware datetimes in Asia/Jerusalem.

    No explicit dates supplied (default board view):
        from_dt = now_il − 1 hour                        (rolling lower bound)
        to_dt   = window_end_dt (DB-derived upper bound)  or None if table empty

    Explicit dates override the default completely.
    Either or both can be None independently.
    """
    if date_from is None and date_to is None:
        if now_il is None:
            now_il = datetime.now(tz=ISRAEL_TZ)
        from_dt = now_il - timedelta(hours=1)
        to_dt = window_end_dt  # None is fine — query will have no upper bound
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

    # Floor the window at the recent-history horizon.
    #
    # This is the only remaining endpoint that serves raw per-flight rows, and the
    # board is a LIVE view -- no user needs individual rows from months ago. The
    # accumulated archive is not reproducible from the IAA feed (it publishes a rolling
    # 4-day window), so raw historical rows are the one thing worth withholding.
    # Historical questions are answered by the aggregate endpoints, which expose
    # statistics rather than records.
    floor = datetime.now(tz=ISRAEL_TZ) - timedelta(days=settings.board_history_days)
    if from_dt and from_dt < floor:
        from_dt = floor
    if to_dt and to_dt < floor:
        to_dt = floor

    # Clamp absurd spans. Without this, date_from=2000-01-01&date_to=2100-01-01 makes
    # the pre-LIMIT scan proportional to table size even though the response is capped.
    max_span = timedelta(days=MAX_WINDOW_DAYS)
    if from_dt and to_dt and (to_dt - from_dt) > max_span:
        to_dt = from_dt + max_span
    elif to_dt and not from_dt:
        from_dt = to_dt - max_span
    elif from_dt and not to_dt:
        to_dt = from_dt + max_span

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
):
    """
    Build and execute the flights query.

    Returns (rows, count, truncated), capped at MAX_BOARD_ROWS. `truncated` is True
    when the window held more rows than were returned, so the client can say the view
    is incomplete instead of silently believing it received everything.

    The cap is what makes response size independent of the filters a client supplies.
    """
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
    # Stable secondary sort guarantees consistent ordering
    query = query.order_by(order_fn, Flight.flight_number.asc())

    # Fetch one extra row to detect truncation without a second COUNT(*) query —
    # which would also hand the client the exact table size.
    rows = query.limit(MAX_BOARD_ROWS + 1).all()
    truncated = len(rows) > MAX_BOARD_ROWS
    rows = rows[:MAX_BOARD_ROWS]
    return rows, len(rows), truncated


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
):
    """
    Server-Sent Events stream for the live flight board.

    • On connect: immediately sends all flights in the current rolling window.
    • Every REFRESH_INTERVAL seconds (15 min): re-queries the DB and pushes a
      full update. The Israel-time window is re-evaluated on every refresh.
    • Every HEARTBEAT_INTERVAL seconds: sends an SSE keepalive comment so that
      proxies and load-balancers don't close the idle connection.
    • At most MAX_BOARD_ROWS flights per event; `truncated` flags a clipped view.
    """
    if _sse_slots.locked():
        # Refuse clearly rather than accept a connection there is no capacity to serve.
        raise HTTPException(
            status_code=503, detail="Flight board at capacity, please retry shortly."
        )

    async def event_stream():
        loop = asyncio.get_running_loop()

        async with _sse_slots:
            while True:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected from flight board")
                    break

                try:
                    def query_db():
                        db = SessionLocal()
                        try:
                            # Re-compute window on every iteration (cutoff advances with real time)
                            window_end_dt = _get_latest_window_end(db)
                            from_dt, to_dt = _compute_date_window(
                                date_from, date_to, window_end_dt=window_end_dt
                            )
                            rows, count, truncated = _build_query(
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
                            )
                            return [_serialize(r) for r in rows], count, truncated
                        finally:
                            db.close()

                    flight_data, count, truncated = await loop.run_in_executor(
                        _board_executor, query_db
                    )

                    payload = json.dumps({
                        "type": "flights",
                        "data": flight_data,
                        # Rows in THIS payload, not the matching-row count: the true
                        # total would tell a scraper the table size.
                        "count": count,
                        "truncated": truncated,
                        "timestamp": datetime.now(tz=ISRAEL_TZ).isoformat(),
                    })
                    yield f"data: {payload}\n\n"

                except Exception as exc:
                    logger.error("SSE stream error", error=str(exc))
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Server error, retrying...'})}\n\n"

                # Sleep REFRESH_INTERVAL total, emitting keepalive comments every
                # HEARTBEAT_INTERVAL seconds so the connection is not dropped as idle.
                elapsed = 0
                while elapsed < REFRESH_INTERVAL:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    elapsed += HEARTBEAT_INTERVAL
                    if elapsed < REFRESH_INTERVAL:
                        if await request.is_disconnected():
                            return
                        yield ": keepalive\n\n"

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
    """
    Return unique airlines, cities, and terminals for populating filter dropdowns.

    Bounded to the recent horizon: without a date floor these three DISTINCT queries
    are unauthenticated full table scans whose cost grows with the table forever. An
    airline that has not flown in months does not belong in a live board's filters.
    """
    try:
        horizon = datetime.now(tz=ISRAEL_TZ) - timedelta(days=settings.options_horizon_days)
        base = db.query(Flight).filter(Flight.scheduled_time >= horizon)
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
