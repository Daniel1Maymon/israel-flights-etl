"""
The /api/v1/flights router has been removed.

It was the proven full-table extraction vector (100% of rows recovered in 31 requests
by partitioning on date), and it served no feature: the only frontend caller,
UnifiedSearch -> DashboardFilters, was unreachable from the app entry point, and its
request used size=200 which the le=50 cap rejected with 422 anyway.

The accumulated archive cannot be re-derived from the IAA feed (rolling 4-day window),
so raw historical rows are the one asset worth withholding. Aggregate endpoints still
cover the full range.

These tests exist so the endpoints are not reintroduced by accident.
"""
import pytest

REMOVED_PATHS = [
    "/api/v1/flights/",
    "/api/v1/flights",
    "/api/v1/flights/airlines",
    "/api/v1/flights/destinations",
]


class TestBulkFlightEndpointsRemoved:

    @pytest.mark.parametrize("path", REMOVED_PATHS)
    def test_endpoint_returns_404(self, client, path):
        assert client.get(path).status_code == 404, (
            f"{path} is reachable again -- this is the bulk extraction vector"
        )

    @pytest.mark.parametrize("path", REMOVED_PATHS)
    def test_endpoint_ignores_filters_and_paging(self, client, sample_flights, path):
        """Still gone regardless of parameters."""
        r = client.get(path, params={"page": 1, "size": 50, "date_from": "2024-01-01"})
        assert r.status_code == 404

    def test_replacement_surfaces_still_work(self, client, sample_flights):
        """Removing the router must not take the live endpoints with it."""
        for path in ("/api/v1/destinations", "/api/v1/flight-board/options"):
            assert client.get(path).status_code == 200, f"{path} broke"
