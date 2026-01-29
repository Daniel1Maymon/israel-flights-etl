# Backend API Tests

This directory contains comprehensive tests for all backend API endpoints.

## Test Structure

- `conftest.py` - Pytest configuration and fixtures
- `test_health_endpoints.py` - Tests for health check endpoints
- `test_flight_endpoints.py` - Tests for flight data endpoints
- `test_airline_endpoints.py` - Tests for airline statistics endpoints
- `test_destination_endpoints.py` - Tests for destination endpoints
- `test_error_handling.py` - Tests for error handling and edge cases

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific test file:
```bash
pytest tests/test_health_endpoints.py
```

### Run specific test class:
```bash
pytest tests/test_flight_endpoints.py::TestFlightListEndpoint
```

### Run specific test:
```bash
pytest tests/test_flight_endpoints.py::TestFlightListEndpoint::test_list_flights_basic
```

### Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

### Run with verbose output:
```bash
pytest -v
```

## Test Coverage

The test suite covers:

1. **Health Endpoints** (`/`, `/health`, `/ready`, `/metrics`)
   - Basic functionality
   - Response structure validation
   - Database connectivity checks

2. **Flight Endpoints** (`/api/v1/flights`)
   - List flights with pagination
   - Filtering (direction, airline, status, terminal, dates, delays)
   - Get flight by ID
   - Search flights
   - Flight statistics
   - Airlines listing
   - Destinations listing

3. **Airline Endpoints** (`/api/v1/airlines`)
   - Airline statistics
   - Top/bottom performing airlines
   - Airline destinations
   - Airline-specific destinations
   - Health check

4. **Destination Endpoints** (`/api/v1/destinations`)
   - List destinations
   - Search destinations
   - Pagination

5. **Error Handling**
   - Invalid endpoints
   - Invalid parameters
   - Edge cases
   - Empty database scenarios

## Test Database

Tests use an in-memory SQLite database that is created and destroyed for each test. This ensures:
- Tests are isolated (each test runs in a transaction that rolls back)
- Tests run quickly (in-memory database)
- No external database dependencies

### Important Notes:

1. **Transaction Isolation**: Each test runs in a transaction that is rolled back after completion. This ensures complete test isolation - no test can affect another.

2. **Type Compatibility**: The Flight model uses PostgreSQL-specific `TIMESTAMP(timezone=True)` types. For SQLite compatibility, these are temporarily converted to `DateTime` during test setup and restored afterward. This is done per-test, not globally, to avoid mutating the production model.

3. **Model Usage**: Tests use the actual `Flight` model from `app.models.flight`, ensuring that endpoints query the correct model structure.

4. **Cleanup**: After each test:
   - Transaction is rolled back (removes all data)
   - Tables are dropped
   - Model types are restored to original values
   - Dependency overrides are cleared

## Fixtures

- `db_session` - Provides a fresh database session for each test
- `client` - Provides a FastAPI test client with database overrides
- `sample_flights` - Creates sample flight data for testing

## Best Practices Followed

1. **Test Isolation**: Each test is completely isolated using transaction rollback
2. **No Global Mutations**: Production models are never permanently modified
3. **Proper Cleanup**: All resources are cleaned up after each test
4. **Real Models**: Tests use actual production models (not test doubles)
5. **Dependency Injection**: FastAPI dependencies are properly overridden for testing
6. **Type Safety**: Type hints are used throughout fixtures

## Notes

- All tests use the `TestClient` from FastAPI for synchronous testing
- Database dependencies (`get_db` and `get_database`) are overridden to use the test database
- Tests are designed to be independent and can run in any order
- Tests use transactions for isolation - data is automatically rolled back after each test
