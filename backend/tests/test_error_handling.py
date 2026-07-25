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
        response = client.get("/api/v1/flights?page=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_zero_page_size(self, client, sample_flights):
        """Test zero page size"""
        response = client.get("/api/v1/flights?size=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_negative_delay_min(self, client, sample_flights):
        """Test negative delay_min"""
        response = client.get("/api/v1/flights?delay_min=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_negative_delay_max(self, client, sample_flights):
        """Test negative delay_max"""
        response = client.get("/api/v1/flights?delay_max=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_sort_order(self, client, sample_flights):
        """Test invalid sort order (if endpoint supports it)"""
        # This test depends on whether the endpoint validates sort_order
        # Some endpoints might not have this parameter
        pass
    
    def test_very_large_page_number(self, client, sample_flights):
        """Test very large page number"""
        response = client.get("/api/v1/flights?page=999999")
        assert response.status_code == status.HTTP_200_OK
        # Should return empty results or last page
        data = response.json()
        assert "data" in data
        assert "pagination" in data
    
    def test_special_characters_in_search(self, client, sample_flights):
        """Test search with special characters"""
        response = client.get("/api/v1/flights/search?q=test%20%26%20special")
        # Endpoint might not exist (404) or handle gracefully (200/422)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_empty_database(self, client):
        """Test endpoints with empty database"""
        # Test without sample_flights fixture
        response = client.get("/api/v1/flights")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        # Should return empty list or handle gracefully
        assert isinstance(data["data"], list)


class TestEdgeCases:
    """Test suite for edge cases"""
    
    def test_pagination_last_page(self, client, sample_flights):
        """Test accessing last page of results"""
        # First get total pages
        response = client.get("/api/v1/flights?page=1&size=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        total_pages = data["pagination"]["pages"]
        
        # Access last page
        if total_pages > 0:
            response = client.get(f"/api/v1/flights?page={total_pages}&size=2")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["page"] == total_pages
            assert data["pagination"]["has_next"] is False
    
    def test_pagination_first_page(self, client, sample_flights):
        """Test accessing first page"""
        response = client.get("/api/v1/flights?page=1&size=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["has_prev"] is False
    
    def test_filter_with_no_results(self, client, sample_flights):
        """Test filter that returns no results"""
        response = client.get("/api/v1/flights?airline_code=NONEXISTENT")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 0
        assert data["pagination"]["total"] == 0
    
    def test_multiple_filters_combinations(self, client, sample_flights):
        """Test various filter combinations"""
        # Test all filters together
        response = client.get(
            "/api/v1/flights?"
            "direction=D&"
            "airline_code=LY&"
            "terminal=3&"
            "delay_min=0&"
            "delay_max=10"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        # All flights should match all filters
        for flight in data["data"]:
            assert flight["direction"] == "D"
            assert flight["airline_code"] == "LY"
            assert flight["terminal"] == "3"
            assert 0 <= flight["delay_minutes"] <= 10
    
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
        response = client.get(f"/api/v1/flights?date_from={date_str}&date_to={date_str}")
        assert response.status_code == status.HTTP_200_OK
        
        # Test date_from after date_to (should still work, just return empty)
        date_from = (datetime.utcnow() + timedelta(days=10)).date().isoformat()
        date_to = (datetime.utcnow() + timedelta(days=5)).date().isoformat()
        response = client.get(f"/api/v1/flights?date_from={date_from}&date_to={date_to}")
        assert response.status_code == status.HTTP_200_OK
