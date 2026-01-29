# Integration Tests - Real Endpoints with Real Database

These tests make **actual HTTP requests** to a **running server** and use **real database data**.

## Prerequisites

1. **Start the server:**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```

2. **Ensure database has data:**
   - Database should be running and accessible
   - Should have flight data loaded

## Running Integration Tests

```bash
# Make sure server is running first!
pytest tests/integration/ -v

# Run specific test file
pytest tests/integration/test_real_endpoints.py -v

# Run with verbose output
pytest tests/integration/ -vv
```

## What These Tests Do

- ✅ Make **real HTTP requests** to `http://localhost:8000`
- ✅ Use **real database** with actual flight data
- ✅ Test **actual endpoints** as they would be used in production
- ✅ Verify **real data** is returned correctly
- ✅ Test **error handling** with real server responses

## Differences from Unit Tests

| Aspect | Unit Tests (`tests/`) | Integration Tests (`tests/integration/`) |
|--------|----------------------|-------------------------------------------|
| Server | ❌ No (TestClient) | ✅ Yes (uvicorn) |
| Database | SQLite (in-memory) | PostgreSQL (real) |
| Data | Mock/test data | Real production data |
| HTTP | Direct function calls | Real HTTP requests |
| Speed | Fast | Slower |
| Use Case | CI/CD, fast feedback | End-to-end validation |

## Test Structure

- `test_real_endpoints.py` - Tests all endpoints with real data
- `conftest.py` - Checks server availability before running tests

## Notes

- Tests will **skip automatically** if server is not running
- Tests use **real database data** - make sure you have data loaded
- These are **slower** than unit tests but test the **full stack**
