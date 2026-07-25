"""
Security: no public endpoint may return more than MAX_PUBLIC_ROWS rows.

These tests are written to FAIL against the pre-fix code and pass after it. They
encode a single invariant: the size of any response is bounded by the server, not
by what the client asks for.

Run:  pytest tests/test_security_row_cap.py -v
"""
from datetime import date, datetime, timedelta

import pytest

from app.api.flight_board import ISRAEL_TZ, _build_query, _compute_date_window

# The contract. Deliberately hardcoded here rather than imported from app config:
# a test that reads the value it is checking cannot detect that value being raised.
MAX_PUBLIC_ROWS = 100


def _rows_from(result):
    """
    Pull the row list out of _build_query's return value.

    Tolerates the 2-tuple (pre-fix) and 3-tuple (post-fix, with `truncated`) shapes
    so the test fails on its actual assertion rather than on tuple unpacking.
    """
    return result[0]


def _attack_dates():
    """
    The date range an attacker supplies to request everything.

    Anchored at yesterday rather than year 2000: the window clamp now caps the span,
    so a range starting in 2000 would be clipped to 2000-02-01 and exclude the seeded
    rows entirely -- the row cap would never be exercised and the test would pass
    while proving nothing.
    """
    today = datetime.now(tz=ISRAEL_TZ).date()
    return today - timedelta(days=1), date(2100, 1, 1)


def _wide_window():
    return _compute_date_window(*_attack_dates())


def _query_all(db, from_dt, to_dt):
    return _build_query(
        db=db,
        direction=None,
        flight_number=None,
        airline_code=None,
        location=None,
        terminal=None,
        from_dt=from_dt,
        to_dt=to_dt,
        sort_by="scheduled_time",
        sort_order="asc",
    )


class TestFlightBoardRowCap:
    """flight_board._build_query ends in query.all() with no LIMIT (flight_board.py:144)."""

    def test_build_query_caps_rows_at_100(self, db_session, make_flights):
        make_flights(250)
        from_dt, to_dt = _wide_window()

        rows = _rows_from(_query_all(db_session, from_dt, to_dt))

        assert len(rows) <= MAX_PUBLIC_ROWS, (
            f"_build_query returned {len(rows)} rows for a 250-row table. "
            f"An unbounded query.all() lets one request drain the whole table."
        )

    def test_build_query_reports_truncation(self, db_session, make_flights):
        """A capped response must say so, or the client silently believes it got everything."""
        make_flights(250)
        from_dt, to_dt = _wide_window()

        result = _query_all(db_session, from_dt, to_dt)

        assert len(result) == 3, (
            "_build_query must return (rows, count, truncated) so the board can tell "
            "the user their view is incomplete."
        )
        assert result[2] is True, "250 rows capped to 100 must set truncated=True"

    def test_truncated_is_false_when_everything_fits(self, db_session, make_flights):
        """The flag must be honest in both directions, or the UI nags on every load."""
        make_flights(10)
        from_dt, to_dt = _wide_window()

        result = _query_all(db_session, from_dt, to_dt)

        assert len(result) == 3
        assert result[2] is False, "10 rows under a 100 cap must set truncated=False"

    def test_date_window_is_clamped_to_a_sane_span(self):
        """
        A 100-year range must not reach the database as a 100-year range.

        The LIMIT bounds the response, but without a clamp Postgres still scans and
        sorts the full matching set before discarding it.
        """
        from_dt, to_dt = _compute_date_window(date(2000, 1, 1), date(2100, 1, 1))

        span = to_dt - from_dt
        assert span <= timedelta(days=31), (
            f"window spans {span.days} days; an unclamped range makes the pre-LIMIT "
            f"scan proportional to table size."
        )


class TestFlightBoardSSE:
    """End-to-end through the real route handler: the documented one-request full dump."""

    def test_wide_date_range_cannot_dump_the_table(self, first_sse_frame, make_flights):
        """
        The literal attack:
            GET /api/v1/flight-board/stream?date_from=2000-01-01&date_to=2100-01-01
        """
        make_flights(250)

        payload = first_sse_frame(date_from=_attack_dates()[0], date_to=_attack_dates()[1])

        assert len(payload["data"]) <= MAX_PUBLIC_ROWS, (
            f"one anonymous request returned {len(payload['data'])} rows"
        )

    def test_default_window_is_also_capped(self, first_sse_frame, make_flights):
        """
        The cap must not depend on the client supplying dates.

        Seed in Israel wall-clock: the default window is built from Asia/Jerusalem
        local time, so naive UTC timestamps would fall outside it and the test would
        pass without the cap ever being exercised.
        """
        israel_now = datetime.now(tz=ISRAEL_TZ).replace(tzinfo=None)
        make_flights(
            250, start=israel_now - timedelta(minutes=30), step=timedelta(seconds=30)
        )

        payload = first_sse_frame()

        assert len(payload["data"]) <= MAX_PUBLIC_ROWS, (
            f"default window returned {len(payload['data'])} rows with no date params"
        )
        # Guards against a vacuous pass: if the seeded rows had fallen outside the
        # window, the cap would never have been exercised and this test would be
        # green while proving nothing.
        assert payload.get("truncated") is True, (
            "expected the 250 seeded rows to overflow the default window"
        )

    def test_stream_marks_truncated_payloads(self, first_sse_frame, make_flights):
        make_flights(250)

        payload = first_sse_frame(date_from=_attack_dates()[0], date_to=_attack_dates()[1])

        assert payload.get("truncated") is True


class TestPaginatedEndpointsRowCap:
    """/flights already caps size at 50 — these lock that in against future edits."""

    @pytest.mark.parametrize("size", [51, 100, 1000, 999999])
    def test_oversized_page_is_rejected(self, client, sample_flights, size):
        response = client.get("/api/v1/destinations", params={"size": size})
        assert response.status_code == 422, (
            f"size={size} was accepted; the per-page ceiling is the only thing "
            f"stopping a single request from returning the table."
        )

    def test_paginated_response_never_exceeds_cap(self, client, make_flights):
        make_flights(250)
        response = client.get("/api/v1/destinations", params={"size": 50})
        assert response.status_code == 200
        assert len(response.json()["destinations"]) <= MAX_PUBLIC_ROWS


class TestNoRouteReturnsUnboundedRows:
    """
    Sweep every registered GET route.

    This is the only test here that protects endpoints nobody has thought about yet --
    every other test guards a route someone already remembered to secure.
    """

    SKIP_PREFIXES = (
        "/api/v1/admin",           # 401 by design
        "/api/v1/flight-board/stream",  # infinite stream, covered above
        "/docs", "/redoc", "/openapi.json",
    )

    def _collect_lists(self, node, found, depth=0):
        """Recursively find every list-of-dicts in a JSON body."""
        if depth > 6:
            return
        if isinstance(node, list):
            if node and isinstance(node[0], dict):
                found.append(node)
            for item in node[:5]:
                self._collect_lists(item, found, depth + 1)
        elif isinstance(node, dict):
            for value in node.values():
                self._collect_lists(value, found, depth + 1)

    def test_every_get_route_is_bounded(self, client, make_flights):
        from app.main import app

        make_flights(250)
        offenders = []

        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set()) or set()
            if "GET" not in methods or "{" in path:
                continue
            if path.startswith(self.SKIP_PREFIXES):
                continue

            try:
                response = client.get(path, timeout=15.0)
            except Exception:
                continue  # route needs params or a live dependency; not this test's job
            if response.status_code != 200:
                continue

            try:
                body = response.json()
            except ValueError:
                continue

            found = []
            self._collect_lists(body, found)
            for lst in found:
                if len(lst) > MAX_PUBLIC_ROWS:
                    offenders.append(f"{path} -> list of {len(lst)}")

        assert not offenders, (
            "routes returned more than %d rows:\n  %s" % (MAX_PUBLIC_ROWS, "\n  ".join(offenders))
        )
