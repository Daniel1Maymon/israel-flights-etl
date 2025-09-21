#!/usr/bin/env python3
"""
Basic API tests for Israel Flights API
Run with: python test_basic.py
"""

import requests
import json
import sys
from typing import Dict, Any


class APITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.passed = 0
        self.failed = 0
    
    def test(self, name: str, test_func):
        """Run a test and track results"""
        try:
            print(f"Testing: {name}")
            result = test_func()
            if result:
                print(f"✓ PASSED: {name}")
                self.passed += 1
            else:
                print(f"✗ FAILED: {name}")
                self.failed += 1
        except Exception as e:
            print(f"✗ ERROR in {name}: {e}")
            self.failed += 1
    
    def test_health_check(self) -> bool:
        """Test health check endpoint"""
        response = self.session.get(f"{self.base_url}/health")
        return response.status_code == 200 and "healthy" in response.json().get("status", "")
    
    def test_readiness_check(self) -> bool:
        """Test readiness check endpoint"""
        response = self.session.get(f"{self.base_url}/ready")
        return response.status_code == 200 and "ready" in response.json().get("status", "")
    
    def test_list_flights(self) -> bool:
        """Test list flights endpoint"""
        response = self.session.get(f"{self.base_url}/api/v1/flights?page=1&size=5")
        if response.status_code != 200:
            return False
        
        data = response.json()
        return "data" in data and "pagination" in data and len(data["data"]) <= 5
    
    def test_single_flight(self) -> bool:
        """Test get single flight endpoint"""
        # First get a flight ID
        response = self.session.get(f"{self.base_url}/api/v1/flights?page=1&size=1")
        if response.status_code != 200:
            return False
        
        flights = response.json().get("data", [])
        if not flights:
            print("  No flights found to test single flight endpoint")
            return True  # Not a failure if no data
        
        flight_id = flights[0]["flight_id"]
        
        # Then get that specific flight
        response = self.session.get(f"{self.base_url}/api/v1/flights/{flight_id}")
        if response.status_code != 200:
            return False
        
        data = response.json()
        return data["flight_id"] == flight_id
    
    def test_search_flights(self) -> bool:
        """Test search flights endpoint"""
        response = self.session.get(f"{self.base_url}/api/v1/flights/search?q=LY&page=1&size=5")
        if response.status_code != 200:
            return False
        
        data = response.json()
        return "data" in data and "pagination" in data
    
    def test_filtering(self) -> bool:
        """Test filtering functionality"""
        response = self.session.get(f"{self.base_url}/api/v1/flights?direction=D&airline_code=LY&page=1&size=5")
        if response.status_code != 200:
            return False
        
        data = response.json()
        flights = data.get("data", [])
        
        # Check that all returned flights match the filters
        for flight in flights:
            if flight.get("direction") != "D":
                return False
            if flight.get("airline_code") != "LY":
                return False
        
        return True
    
    def test_airlines_endpoint(self) -> bool:
        """Test airlines endpoint"""
        response = self.session.get(f"{self.base_url}/api/v1/flights/airlines")
        return response.status_code == 200 and isinstance(response.json(), list)
    
    def test_destinations_endpoint(self) -> bool:
        """Test destinations endpoint"""
        response = self.session.get(f"{self.base_url}/api/v1/flights/destinations")
        return response.status_code == 200 and isinstance(response.json(), list)
    
    def test_stats_endpoint(self) -> bool:
        """Test statistics endpoint"""
        response = self.session.get(f"{self.base_url}/api/v1/flights/stats")
        if response.status_code != 200:
            return False
        
        data = response.json()
        required_fields = ["total_flights", "on_time_flights", "delayed_flights", "average_delay"]
        return all(field in data for field in required_fields)
    
    def test_pagination(self) -> bool:
        """Test pagination functionality"""
        # Test page 1
        response1 = self.session.get(f"{self.base_url}/api/v1/flights?page=1&size=2")
        if response1.status_code != 200:
            return False
        
        data1 = response1.json()
        if not data1.get("pagination", {}).get("has_next", False):
            print("  Only one page available, pagination test limited")
            return True
        
        # Test page 2
        response2 = self.session.get(f"{self.base_url}/api/v1/flights?page=2&size=2")
        if response2.status_code != 200:
            return False
        
        data2 = response2.json()
        
        # Check that pages are different
        page1_ids = {flight["flight_id"] for flight in data1.get("data", [])}
        page2_ids = {flight["flight_id"] for flight in data2.get("data", [])}
        
        return len(page1_ids.intersection(page2_ids)) == 0
    
    def test_error_handling(self) -> bool:
        """Test error handling"""
        # Test invalid flight ID
        response = self.session.get(f"{self.base_url}/api/v1/flights/invalid-id")
        if response.status_code != 404:
            return False
        
        # Test invalid pagination
        response = self.session.get(f"{self.base_url}/api/v1/flights?page=0")
        if response.status_code != 400:
            return False
        
        response = self.session.get(f"{self.base_url}/api/v1/flights?size=500")
        if response.status_code != 400:
            return False
        
        return True
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting Israel Flights API Tests")
        print("=" * 50)
        
        # Core functionality tests
        self.test("Health Check", self.test_health_check)
        self.test("Readiness Check", self.test_readiness_check)
        self.test("List Flights", self.test_list_flights)
        self.test("Single Flight", self.test_single_flight)
        self.test("Search Flights", self.test_search_flights)
        self.test("Airlines Endpoint", self.test_airlines_endpoint)
        self.test("Destinations Endpoint", self.test_destinations_endpoint)
        self.test("Stats Endpoint", self.test_stats_endpoint)
        
        # Advanced functionality tests
        self.test("Filtering", self.test_filtering)
        self.test("Pagination", self.test_pagination)
        self.test("Error Handling", self.test_error_handling)
        
        # Summary
        print("=" * 50)
        print(f"Tests completed: {self.passed + self.failed}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        
        if self.failed == 0:
            print("All tests passed!")
            return True
        else:
            print(f"{self.failed} tests failed!")
            return False


def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Israel Flights API")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    
    tester = APITester(args.url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

