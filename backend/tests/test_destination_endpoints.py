"""
Tests for destination endpoints
"""
import pytest
from fastapi import status


class TestDestinationEndpoints:
    """Test suite for destination endpoints"""
    
    def test_list_destinations_basic(self, client, sample_flights):
        """Test basic destination listing"""
        response = client.get("/api/v1/destinations")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
        # total_count / total_pages intentionally removed: an exact row count tells a
        # scraper the table size and how many pages to walk. has_more replaces them.
        assert "total_count" not in data
        assert "total_pages" not in data
        assert "page" in data
        assert "size" in data
        assert "has_more" in data
        assert isinstance(data["destinations"], list)
        assert len(data["destinations"]) > 0
    
    def test_list_destinations_with_search(self, client, sample_flights):
        """Test destination listing with search"""
        response = client.get("/api/v1/destinations?search=New")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
        # All results should contain "New" in destination name
        for dest in data["destinations"]:
            assert "New" in dest["destination"]
    
    def test_list_destinations_pagination(self, client, sample_flights):
        """Test destination listing with pagination"""
        response = client.get("/api/v1/destinations?page=1&size=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["destinations"]) <= 2
        assert data["page"] == 1
        assert data["size"] == 2
        assert "total_pages" not in data
        assert "has_more" in data
    
    def test_list_destinations_invalid_page(self, client, sample_flights):
        """Test destination listing with invalid page"""
        response = client.get("/api/v1/destinations?page=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_list_destinations_invalid_size(self, client, sample_flights):
        """Test destination listing with invalid size"""
        response = client.get("/api/v1/destinations?size=500")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_list_destinations_empty_search(self, client, sample_flights):
        """Test destination listing with empty search (should return all)"""
        response = client.get("/api/v1/destinations?search=")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
    
    def test_list_destinations_structure(self, client, sample_flights):
        """Test destination response structure"""
        response = client.get("/api/v1/destinations")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        if len(data["destinations"]) > 0:
            dest = data["destinations"][0]
            assert "destination" in dest
            assert isinstance(dest["destination"], str)
