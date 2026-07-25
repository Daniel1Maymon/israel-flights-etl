"""
Security: bulk-collection and resource-exhaustion guards.

The row cap (test_security_row_cap.py) bounds ONE response. It does not stop an
attacker looping. These tests cover the controls that bound the loop: offset depth,
rate limiting, exact-total disclosure, and unbounded scans.

Note on fidelity: these run against in-memory SQLite, so they verify the *contract*
(status codes, counts, headers) and not query plans. Whether LIMIT actually prevents
Postgres from sorting the full table needs EXPLAIN ANALYZE against real Postgres --
out of scope here, tracked separately.

Run:  pytest tests/test_security_dos.py -v
"""
import pytest


class TestDeepPaginationRejected:
    """
    page is only validated ge=1 (flights.py:25), so offset = (page-1)*size is
    unbounded. OFFSET 5000000 makes Postgres materialise and discard 5M sorted rows
    to return 50 -- the most expensive request in the API, free to send.
    """

    @pytest.mark.parametrize("page", [202, 1000, 100000, 999999])
    def test_deep_page_is_rejected(self, client, sample_flights, page):
        response = client.get("/api/v1/destinations", params={"page": page, "size": 50})
        assert response.status_code == 400, (
            f"page={page} returned {response.status_code}; deep offsets must be "
            f"refused, not served."
        )

    def test_offset_boundary_is_exact(self, client, sample_flights):
        """
        max_offset is 10_000: skipping exactly 10_000 rows is allowed, 10_050 is not.

        Pinned explicitly because an off-by-one here either breaks the last legitimate
        page or leaves a free extra page of enumeration.
        """
        ok = client.get("/api/v1/destinations", params={"page": 201, "size": 50})
        assert ok.status_code == 200, "offset exactly at the cap must still be served"

        blocked = client.get("/api/v1/destinations", params={"page": 202, "size": 50})
        assert blocked.status_code == 400, "offset past the cap must be refused"

    def test_shallow_pages_still_work(self, client, make_flights):
        """The guard must not break normal browsing."""
        make_flights(120)
        for page in (1, 2, 3):
            response = client.get("/api/v1/destinations", params={"page": page, "size": 50})
            assert response.status_code == 200, f"page={page} broke legitimate paging"

    @pytest.mark.parametrize("path", [
        "/api/v1/destinations",
        "/api/v1/destinations",
        "/api/v1/destinations/",
    ])
    def test_deep_page_rejected_on_every_paginated_route(self, client, sample_flights, path):
        response = client.get(path, params={"page": 100000, "size": 50})
        assert response.status_code in (400, 404), (
            f"{path} served an unbounded offset"
        )


class TestTotalsNotDisclosed:
    """
    pagination.total tells a scraper exactly how many pages to pull and how large
    the table is. Replaced by has_more.
    """

    def test_paginated_route_does_not_report_exact_total(self, client, make_flights):
        make_flights(120)
        body = client.get("/api/v1/destinations", params={"size": 50}).json()

        assert "total_count" not in body, (
            "an exact count discloses table size and gives a scraper a page count"
        )
        assert "total_pages" not in body
        assert "has_more" in body, "clients still need a next-page signal"

    def test_board_does_not_report_exact_total(self, first_sse_frame, make_flights):
        """The SSE payload's `total` is the same disclosure in a different shape."""
        from tests.test_security_row_cap import _attack_dates

        make_flights(250)
        date_from, date_to = _attack_dates()
        payload = first_sse_frame(date_from=date_from, date_to=date_to)

        assert payload.get("total") != 250, (
            "payload.total revealed the true matching-row count (250) despite the cap"
        )


class TestRateLimiting:
    """
    settings.rate_limit_per_minute (config.py:88) is read by nothing -- no limiter
    middleware is installed in main.py. Without it, the row cap just sets the cost
    per request; nothing bounds requests per minute.
    """

    def test_burst_gets_rate_limited(self, client, sample_flights):
        statuses = [
            client.get("/api/v1/destinations", params={"size": 1}).status_code
            for _ in range(130)
        ]

        assert 429 in statuses, (
            f"130 requests in one burst produced no 429. Status counts: "
            f"{ {s: statuses.count(s) for s in set(statuses)} }"
        )

    def test_rate_limited_response_tells_client_when_to_retry(self, client, sample_flights):
        last = None
        for _ in range(130):
            response = client.get("/api/v1/destinations", params={"size": 1})
            if response.status_code == 429:
                last = response
                break

        assert last is not None, "never reached the limit"
        assert "retry-after" in {k.lower() for k in last.headers}, (
            "429 without Retry-After makes well-behaved clients guess"
        )


class TestUnboundedScans:
    """
    /flight-board/options runs three DISTINCT queries over the entire table with no
    date bound, unauthenticated, on every call.
    """

    def test_options_excludes_stale_rows(self, client, db_session, make_flights):
        from datetime import datetime, timedelta

        make_flights(5)  # recent
        old = make_flights(1, start=datetime.utcnow() - timedelta(days=800))
        old[0].airline_name = "Ancient Air"
        old[0].airline_code = "ZZ"
        old[0].location_en = "Atlantis"
        db_session.commit()

        response = client.get("/api/v1/flight-board/options")
        assert response.status_code == 200

        assert "Atlantis" not in response.text, (
            "options surfaced a row from 800 days ago; without a date floor this is "
            "an unauthenticated full table scan, three times per call."
        )
