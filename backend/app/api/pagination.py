"""Shared pagination guards."""
from fastapi import HTTPException

from app.config import settings


def check_offset(page: int, size: int) -> int:
    """
    Reject page depths that make a single request disproportionately expensive.

    OFFSET n forces Postgres to materialise and discard n sorted rows to return `size`,
    so deep pages are the costliest requests in the API and are free to send. Capping
    the offset also slows a scraper walking the table page by page.

    Note this bounds depth WITHIN one result set. A client that varies filters (dates,
    airline, terminal) gets a fresh offset space each time, so this is a cost control,
    not an anti-extraction control.
    """
    offset = (page - 1) * size
    if offset > settings.max_offset:
        raise HTTPException(
            status_code=400,
            detail=(
                "Result set too deep. Narrow the range with date_from/date_to "
                "or add a filter."
            ),
        )
    return offset
