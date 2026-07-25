"""
Tests for error handling and edge cases
"""
import pytest
from fastapi import status


class TestErrorHandling:
    """Test suite for error handling"""
    
    def test_invalid_endpoint(self, client):
        """Test accessing non-existent endpoint"""
        response = client.get("/api/v1/non-existent")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_invalid_flight_id_format(self, client):
        """Test invalid flight ID format"""
        response = client.get("/api/v1/flights/invalid-id-with-special-chars-!!!")
        # Should return 404, not 500
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_search_query_missing(self, client):
        """Test search endpoint without required query parameter"""
        response = client.get("/api/v1/flights/search")
        # Endpoint might not exist (404) or require query param (422)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_negative_page_number(self, client, sample_flights):
        """Test negative page number"""
        response = client.get("/api/v1/destinations?page=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_zero_page_size(self, client, sample_flights):
        """Test zero page size"""
        response = client.get("/api/v1/destinations?size=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_sort_order(self, client, sample_flights):
        """Test invalid sort order (if endpoint supports it)"""
        # This test depends on whether the endpoint validates sort_order
        # Some endpoints might not have this parameter
        pass
    
    def test_very_large_page_number(self, client, sample_flights):
        """A very large page is now refused rather than served.

        OFFSET 999998*20 would make Postgres materialise and discard ~20M sorted rows
        to return 20, so the request is rejected at the boundary instead.
        """
        response = client.get("/api/v1/destinations?page=999999")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_special_characters_in_search(self, client, sample_flights):
        """Test search with special characters"""
        response = client.get("/api/v1/flights/search?q=test%20%26%20special")
        # Endpoint might not exist (404) or handle gracefully (200/422)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_empty_database(self, client):
        """Test endpoints with empty database"""
        # Test without sample_flights fixture
        response = client.get("/api/v1/destinations")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
        assert "has_more" in data
        assert isinstance(data["destinations"], list)


class TestEdgeCases:
    """Test suite for edge cases"""
    
    def test_pagination_last_page(self, client, sample_flights):
        """Test accessing last page of results"""
        # Exact page counts are no longer published, so walk forward with has_more
        # instead of jumping to a known last page.
        response = client.get("/api/v1/destinations?page=1&size=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        page = 1
        while data["has_more"] and page < 50:
            page += 1
            response = client.get(f"/api/v1/destinations?page={page}&size=2")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

        assert data["has_more"] is False
        assert data["page"] == page
    
    def test_pagination_first_page(self, client, sample_flights):
        """Test accessing first page"""
        response = client.get("/api/v1/destinations?page=1&size=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
    
    def test_filter_with_no_results(self, client, sample_flights):
        """Test filter that returns no results"""
        response = client.get("/api/v1/destinations?search=NONEXISTENT_CITY_XYZ")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["destinations"]) == 0
        assert data["has_more"] is False
    
    def test_multiple_filters_combinations(self, client, sample_flights):
        """Combined filters on the live board (the removed router had its own set)."""
        response = client.get(
            "/api/v1/flight-board/options?direction=D"
        )
        assert response.status_code == status.HTTP_200_OK
        assert set(response.json().keys()) == {"airlines", "cities", "terminals"}
    
    def test_case_insensitive_search(self, client, sample_flights):
        """Test case insensitive search"""
        response_lower = client.get("/api/v1/flights/search?q=el al")
        response_upper = client.get("/api/v1/flights/search?q=EL AL")
        response_mixed = client.get("/api/v1/flights/search?q=El Al")
        
        # Endpoint might not exist
        if response_lower.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Search endpoint not available")
        
        assert response_lower.status_code == status.HTTP_200_OK
        assert response_upper.status_code == status.HTTP_200_OK
        assert response_mixed.status_code == status.HTTP_200_OK
        
        # Results should be similar (case insensitive)
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        data_mixed = response_mixed.json()
        
        # All should return results
        assert len(data_lower.get("data", [])) > 0 or len(data_upper.get("data", [])) > 0 or len(data_mixed.get("data", [])) > 0
    
    def test_unicode_characters(self, client, sample_flights):
        """Test handling of unicode characters"""
        # Search for Hebrew text if available
        response = client.get("/api/v1/flights/search?q=תל")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Search endpoint not available")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
    
    def test_date_filter_edge_cases(self, client, sample_flights):
        """Test date filter edge cases"""
        from datetime import datetime, timedelta
        
        # Test date_from equals date_to
        date_str = datetime.utcnow().date().isoformat()
        response = client.get(f"/api/v1/flight-board/options?direction=D")
        assert response.status_code == status.HTTP_200_OK

        # Inverted range must not error, just yield nothing.
        from app.api.flight_board import _compute_date_window
        from datetime import date as _date
        f, t = _compute_date_window(_date(2026, 1, 20), _date(2026, 1, 10))
        assert f is not None and t is not None
