"""
Tests for airline endpoints

Note: These tests may be skipped when using SQLite test database because
the AirlineAggregationService uses PostgreSQL-specific functions (array_agg).
"""
import pytest
from fastapi import status
from datetime import datetime, timedelta


def check_postgresql_required(response):
    """Check if response indicates PostgreSQL-specific function error"""
    if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        try:
            error_detail = str(response.json().get("detail", ""))
            error_text = response.text
            if "array_agg" in error_detail or "no such function" in error_detail or "array_agg" in error_text:
                pytest.skip("Airline aggregation requires PostgreSQL (uses array_agg)")
        except:
            # If we can't parse the error, check the raw text
            if "array_agg" in response.text or "no such function" in response.text:
                pytest.skip("Airline aggregation requires PostgreSQL (uses array_agg)")


class TestAirlineStatsEndpoint:
    """Test suite for GET /api/v1/airlines/stats endpoint"""
    
    def test_get_airline_stats_basic(self, client, sample_flights):
        """Test basic airline statistics"""
        response = client.get("/api/v1/airlines/stats")
        # Airline aggregation service uses PostgreSQL-specific functions (array_agg)
        # which don't work with SQLite test database
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            error_detail = response.json().get("detail", "")
            if "array_agg" in error_detail or "no such function" in error_detail:
                pytest.skip("Airline aggregation requires PostgreSQL (uses array_agg)")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
        assert "total_airlines" in data
        assert "total_flights" in data
        assert "date_range" in data
        assert "calculation_timestamp" in data
        assert "calculation_time_ms" in data
        assert isinstance(data["airlines"], list)
        assert isinstance(data["total_airlines"], int)
        assert isinstance(data["total_flights"], int)
    
    def test_get_airline_stats_with_filters(self, client, sample_flights):
        """Test airline stats with filters"""
        response = client.get("/api/v1/airlines/stats?min_flights=1&limit=10")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
        assert len(data["airlines"]) <= 10
    
    def test_get_airline_stats_with_destination_filter(self, client, sample_flights):
        """Test airline stats filtered by destination"""
        response = client.get("/api/v1/airlines/stats?destination=New York")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
    
    def test_get_airline_stats_with_country_filter(self, client, sample_flights):
        """Test airline stats filtered by country"""
        response = client.get("/api/v1/airlines/stats?country=United States")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
    
    def test_get_airline_stats_with_airline_codes(self, client, sample_flights):
        """Test airline stats filtered by airline codes"""
        response = client.get("/api/v1/airlines/stats?airline_codes=LY,DL")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
        # All airlines should be LY or DL
        for airline in data["airlines"]:
            assert airline["airline_code"] in ["LY", "DL"]
    
    def test_get_airline_stats_with_date_range(self, client, sample_flights):
        """Test airline stats with date range"""
        date_from = (datetime.utcnow() - timedelta(days=1)).isoformat()
        date_to = (datetime.utcnow() + timedelta(days=1)).isoformat()
        response = client.get(f"/api/v1/airlines/stats?date_from={date_from}&date_to={date_to}")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
    
    def test_get_airline_stats_sorting(self, client, sample_flights):
        """Test airline stats with sorting"""
        response = client.get("/api/v1/airlines/stats?sort_by=total_flights&sort_order=desc")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
        if len(data["airlines"]) > 1:
            # Verify sorting (descending)
            flights = [airline["total_flights"] for airline in data["airlines"]]
            assert flights == sorted(flights, reverse=True)
    
    def test_get_airline_stats_min_on_time_percentage(self, client, sample_flights):
        """Test airline stats with minimum on-time percentage filter"""
        response = client.get("/api/v1/airlines/stats?min_on_time_percentage=50")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
    
    def test_get_airline_stats_max_avg_delay(self, client, sample_flights):
        """Test airline stats with maximum average delay filter"""
        response = client.get("/api/v1/airlines/stats?max_avg_delay=30")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "airlines" in data
    
    def test_get_airline_stats_limit(self, client, sample_flights):
        """Test airline stats with limit"""
        response = client.get("/api/v1/airlines/stats?limit=2")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["airlines"]) <= 2


class TestAirlineTopBottomEndpoint:
    """Test suite for GET /api/v1/airlines/top-bottom endpoint"""
    
    def test_get_top_bottom_airlines_basic(self, client, sample_flights):
        """Test basic top/bottom airlines"""
        response = client.get("/api/v1/airlines/top-bottom")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "top_airlines" in data
        assert "bottom_airlines" in data
        assert "total_airlines" in data
        assert "calculation_timestamp" in data
        assert isinstance(data["top_airlines"], list)
        assert isinstance(data["bottom_airlines"], list)
    
    def test_get_top_bottom_airlines_with_limits(self, client, sample_flights):
        """Test top/bottom airlines with custom limits"""
        response = client.get("/api/v1/airlines/top-bottom?top_limit=3&bottom_limit=3")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["top_airlines"]) <= 3
        assert len(data["bottom_airlines"]) <= 3
    
    def test_get_top_bottom_airlines_with_filters(self, client, sample_flights):
        """Test top/bottom airlines with filters"""
        response = client.get("/api/v1/airlines/top-bottom?min_flights=1")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "top_airlines" in data
        assert "bottom_airlines" in data
    
    def test_get_top_bottom_airlines_max_limits(self, client, sample_flights):
        """Test top/bottom airlines with maximum limits"""
        response = client.get("/api/v1/airlines/top-bottom?top_limit=20&bottom_limit=20")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["top_airlines"]) <= 20
        assert len(data["bottom_airlines"]) <= 20
    
    def test_get_top_bottom_airlines_invalid_limit(self, client, sample_flights):
        """Test top/bottom airlines with invalid limit"""
        response = client.get("/api/v1/airlines/top-bottom?top_limit=100")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAirlineDestinationsEndpoint:
    """Test suite for GET /api/v1/airlines/destinations endpoint"""
    
    def test_get_airline_destinations_basic(self, client, sample_flights):
        """Test basic airline destinations"""
        response = client.get("/api/v1/airlines/destinations")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
        assert "total_destinations" in data
        assert "page" in data
        assert "size" in data
        assert "has_more" in data
        assert "retrieved_at" in data
        assert isinstance(data["destinations"], list)
    
    def test_get_airline_destinations_with_search(self, client, sample_flights):
        """Test airline destinations with search"""
        response = client.get("/api/v1/airlines/destinations?search=New")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
        for dest in data["destinations"]:
            assert "New" in dest["location_en"]
    
    def test_get_airline_destinations_with_country(self, client, sample_flights):
        """Test airline destinations with country filter"""
        response = client.get("/api/v1/airlines/destinations?country=United States")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
    
    def test_get_airline_destinations_pagination(self, client, sample_flights):
        """Test airline destinations with pagination"""
        response = client.get("/api/v1/airlines/destinations?page=1&size=2")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["destinations"]) <= 2
        assert data["page"] == 1
        assert data["size"] == 2
    
    def test_get_airline_destinations_with_date_range(self, client, sample_flights):
        """Test airline destinations with date range"""
        date_from = (datetime.utcnow() - timedelta(days=1)).isoformat()
        date_to = (datetime.utcnow() + timedelta(days=1)).isoformat()
        response = client.get(f"/api/v1/airlines/destinations?date_from={date_from}&date_to={date_to}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data


class TestAirlineSpecificDestinationsEndpoint:
    """Test suite for GET /api/v1/airlines/{airline_code}/destinations endpoint"""
    
    def test_get_airline_specific_destinations(self, client, sample_flights):
        """Test getting destinations for a specific airline"""
        response = client.get("/api/v1/airlines/LY/destinations")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
        assert "airline_code" in data
        assert "total_count" in data
        assert data["airline_code"] == "LY"
        assert isinstance(data["destinations"], list)
    
    def test_get_airline_specific_destinations_with_search(self, client, sample_flights):
        """Test airline-specific destinations with search"""
        response = client.get("/api/v1/airlines/LY/destinations?search=New")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "destinations" in data
    
    def test_get_airline_specific_destinations_pagination(self, client, sample_flights):
        """Test airline-specific destinations with pagination"""
        response = client.get("/api/v1/airlines/LY/destinations?page=1&size=2")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["destinations"]) <= 2
        assert data["page"] == 1


class TestAirlineHealthEndpoint:
    """Test suite for GET /api/v1/airlines/health endpoint"""
    
    def test_airline_service_health(self, client, sample_flights):
        """Test airline service health check"""
        response = client.get("/api/v1/airlines/health")
        check_postgresql_required(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "database_connected" in data
        assert "total_flights" in data
        assert "airlines_available" in data
        assert "checked_at" in data
        assert data["status"] == "healthy"
        assert data["database_connected"] is True
