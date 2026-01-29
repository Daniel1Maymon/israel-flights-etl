"""
Integration test configuration - tests against REAL running server and database

These tests require:
1. Server running: uvicorn app.main:app --reload
2. Real database with actual data
3. Real HTTP requests to localhost:8000
"""
import pytest
import requests
import time
from typing import Generator

# Base URL for the running server
BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def server_available() -> bool:
    """
    Check if server is running before running integration tests.
    Skips all tests if server is not available.
    """
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pass
    
    pytest.skip("Server not running. Start with: uvicorn app.main:app --reload")


@pytest.fixture(scope="function")
def client(server_available):
    """
    HTTP client for making real requests to the running server.
    Uses requests library to make actual HTTP calls.
    """
    return requests.Session()


@pytest.fixture(scope="session", autouse=True)
def wait_for_server():
    """Wait for server to be ready before running tests"""
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=1)
            if response.status_code == 200:
                return
        except:
            pass
        if i < max_retries - 1:
            time.sleep(0.5)
    
    pytest.skip("Server not available after waiting")
