# Quick Start: Integration Tests with Real Server & Database

## What These Tests Do

✅ Make **real HTTP requests** to your running server  
✅ Use **real PostgreSQL database** with actual flight data  
✅ Test endpoints **exactly as they work in production**  
✅ Verify **real data** is returned correctly  

## Setup

### 1. Start the Server

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

The server should be running on `http://localhost:8000`

### 2. Verify Server is Running

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy",...}
```

### 3. Run Integration Tests

```bash
# In a different terminal (server should still be running)
cd backend
source venv/bin/activate
pytest tests/integration/ -v
```

## Test Results

**17 tests passing** - All endpoints tested with real data!

- ✅ Health endpoints (root, health, ready)
- ✅ Flight listing with real data
- ✅ Pagination with real data
- ✅ Filtering (direction, airline) with real data
- ✅ Airlines listing with real data
- ✅ Destinations listing with real data
- ✅ Airline statistics with real data
- ✅ Error handling

## What Gets Tested

### Real Data Verification
- Tests use actual flights from your database
- Tests verify real airline codes, destinations, etc.
- Tests check actual pagination with real data counts
- Tests verify filters work with real database queries

### Real HTTP Requests
- Tests make actual HTTP GET requests
- Tests go through full request/response cycle
- Tests verify real status codes and response formats
- Tests check actual error responses

## Example Test Output

```
tests/integration/test_real_endpoints.py::TestRealFlightEndpoints::test_list_flights_real_data PASSED
tests/integration/test_real_endpoints.py::TestRealFlightEndpoints::test_filter_flights_by_airline_real PASSED
tests/integration/test_real_endpoints.py::TestRealAirlineStatsEndpoints::test_airline_stats_real_data PASSED
...
================== 17 passed, 1 skipped ===================
```

## Notes

- Tests will **automatically skip** if server is not running
- Tests use **real database** - make sure you have data loaded
- These are **slower** than unit tests but test the **full stack**
- Perfect for **end-to-end validation** before deployment

## Running Both Test Suites

```bash
# Unit tests (fast, no server needed)
pytest tests/ -v

# Integration tests (real server + database)
pytest tests/integration/ -v

# Both together
pytest tests/ tests/integration/ -v
```
