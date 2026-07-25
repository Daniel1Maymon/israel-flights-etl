"""
Tests for health and status endpoints
"""
import pytest
from fastapi import status


class TestHealthEndpoints:
    """Test suite for health check endpoints"""
    
    def test_root_endpoint(self, client):
        """Test API root endpoint"""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
        assert data["message"] == "Israel Flights API"
    
    def test_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert data["status"] == "healthy"
    
    def test_readiness_check(self, client, db_session):
        """Test readiness check endpoint"""
        response = client.get("/ready")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "timestamp" in data
        # Status should be ready if database is connected
        assert data["status"] in ["ready", "not_ready"]
        assert data["database"] in ["healthy", "unhealthy"]
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "timestamp" in data
        assert "uptime" in data
        assert "version" in data
