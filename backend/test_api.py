#!/usr/bin/env python3
"""
Comprehensive API testing script for Israel Flights API
Run this after starting the server with: uvicorn app.main:app --reload
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_endpoint(method: str, endpoint: str, params: Dict[str, Any] = None, expected_status: int = 200) -> bool:
    """Test a single endpoint and return success status"""
    try:
        url = f"{BASE_URL}{endpoint}"
        print(f"Testing {method} {endpoint}...")
        
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=params)
        else:
            print(f"Unsupported method: {method}")
            return False
        
        if response.status_code == expected_status:
            print(f"✅ {method} {endpoint} - Status: {response.status_code}")
            return True
        else:
            print(f"❌ {method} {endpoint} - Expected: {expected_status}, Got: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ {method} {endpoint} - Connection failed (is server running?)")
        return False
    except Exception as e:
        print(f"❌ {method} {endpoint} - Error: {e}")
        return False

def test_health_checks():
    """Test health check endpoints"""
    print("\n🏥 Testing Health Checks...")
    tests = [
        ("GET", "/health", None, 200),
        ("GET", "/ready", None, 200),
        ("GET", "/metrics", None, 200),
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_api_root():
    """Test API root endpoint"""
    print("\n🏠 Testing API Root...")
    return test_endpoint("GET", "/", None, 200)

def test_flights_endpoints():
    """Test flights endpoints"""
    print("\n✈️ Testing Flights Endpoints...")
    tests = [
        ("GET", "/api/v1/flights", {"page": 1, "size": 5}, 200),
        ("GET", "/api/v1/flights", {"page": 1, "size": 50}, 200),
        ("GET", "/api/v1/flights", {"direction": "D", "page": 1, "size": 3}, 200),
        ("GET", "/api/v1/flights", {"airline_code": "LY", "page": 1, "size": 3}, 200),
        ("GET", "/api/v1/flights", {"status": "On Time", "page": 1, "size": 3}, 200),
        ("GET", "/api/v1/flights", {"terminal": "3", "page": 1, "size": 3}, 200),
        ("GET", "/api/v1/flights", {"delay_min": 10, "page": 1, "size": 3}, 200),
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_search_endpoints():
    """Test search endpoints"""
    print("\n🔍 Testing Search Endpoints...")
    tests = [
        ("GET", "/api/v1/flights/search", {"q": "El Al", "page": 1, "size": 3}, 200),
        ("GET", "/api/v1/flights/search", {"q": "Tel Aviv", "page": 1, "size": 3}, 200),
        ("GET", "/api/v1/flights/search", {"q": "LY", "page": 1, "size": 3}, 200),
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_single_flight():
    """Test single flight endpoint"""
    print("\n🎯 Testing Single Flight...")
    try:
        # First get a flight ID
        response = requests.get(f"{BASE_URL}/api/v1/flights?page=1&size=1")
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                flight_id = data["data"][0]["flight_id"]
                return test_endpoint("GET", f"/api/v1/flights/{flight_id}", None, 200)
            else:
                print("❌ No flights found to test single flight endpoint")
                return False
        else:
            print("❌ Failed to get flights list for single flight test")
            return False
    except Exception as e:
        print(f"❌ Error testing single flight: {e}")
        return False

def test_stats_endpoints():
    """Test statistics endpoints"""
    print("\n📊 Testing Statistics Endpoints...")
    tests = [
        ("GET", "/api/v1/flights/stats", None, 200),
        ("GET", "/api/v1/flights/stats", {"group_by": "airline"}, 200),
        ("GET", "/api/v1/flights/stats", {"group_by": "destination"}, 200),
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_airlines_endpoints():
    """Test airlines endpoints"""
    print("\n🏢 Testing Airlines Endpoints...")
    tests = [
        ("GET", "/api/v1/airlines", None, 200),
        ("GET", "/api/v1/airlines", {"search": "El Al"}, 200),
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_destinations_endpoints():
    """Test destinations endpoints"""
    print("\n🌍 Testing Destinations Endpoints...")
    tests = [
        ("GET", "/api/v1/destinations", None, 200),
        ("GET", "/api/v1/destinations", {"search": "Tel Aviv"}, 200),
        ("GET", "/api/v1/destinations", {"country": "Israel"}, 200),
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_error_handling():
    """Test error handling"""
    print("\n⚠️ Testing Error Handling...")
    tests = [
        ("GET", "/api/v1/flights/invalid-id", None, 404),
        ("GET", "/api/v1/flights", {"page": 0}, 400),  # Invalid page
        ("GET", "/api/v1/flights", {"size": 500}, 400),  # Oversized page
        ("GET", "/api/v1/flights/search", {"q": "a"}, 400),  # Query too short
    ]
    
    results = []
    for method, endpoint, params, expected_status in tests:
        results.append(test_endpoint(method, endpoint, params, expected_status))
    
    return all(results)

def test_pagination():
    """Test pagination functionality"""
    print("\n📄 Testing Pagination...")
    try:
        # Test page 1
        response = requests.get(f"{BASE_URL}/api/v1/flights?page=1&size=3")
        if response.status_code != 200:
            print("❌ Page 1 failed")
            return False
        
        data = response.json()
        if "pagination" not in data:
            print("❌ No pagination info in response")
            return False
        
        pagination = data["pagination"]
        required_fields = ["page", "size", "total", "pages", "has_next", "has_prev"]
        for field in required_fields:
            if field not in pagination:
                print(f"❌ Missing pagination field: {field}")
                return False
        
        print(f"✅ Pagination info: page={pagination['page']}, size={pagination['size']}, total={pagination['total']}")
        return True
        
    except Exception as e:
        print(f"❌ Error testing pagination: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Israel Flights API Tests")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not running or not healthy")
            print("Please start the server with: uvicorn app.main:app --reload")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server")
        print("Please start the server with: uvicorn app.main:app --reload")
        return
    
    print("✅ Server is running and healthy")
    
    # Run all test suites
    test_suites = [
        ("Health Checks", test_health_checks),
        ("API Root", test_api_root),
        ("Flights Endpoints", test_flights_endpoints),
        ("Search Endpoints", test_search_endpoints),
        ("Single Flight", test_single_flight),
        ("Statistics Endpoints", test_stats_endpoints),
        ("Airlines Endpoints", test_airlines_endpoints),
        ("Destinations Endpoints", test_destinations_endpoints),
        ("Pagination", test_pagination),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for suite_name, test_func in test_suites:
        print(f"\n{'='*20} {suite_name} {'='*20}")
        success = test_func()
        results.append((suite_name, success))
    
    # Summary
    print("\n" + "="*50)
    print("📋 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for suite_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {suite_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All tests passed! Your API is working perfectly!")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
