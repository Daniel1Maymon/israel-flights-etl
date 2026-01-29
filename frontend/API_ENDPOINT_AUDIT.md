# Frontend API Endpoint Audit

## Current Frontend Endpoints (config/api.ts)

✅ **Correct Endpoints:**
- `/api/v1/flights` - ✅ Matches backend
- `/api/v1/airlines/stats` - ✅ Matches backend  
- `/api/v1/airlines/{airline}/destinations` - ✅ Matches backend
- `/api/v1/destinations` - ✅ Matches backend
- `/api/v1/flights/airlines` - ✅ Matches backend

## Issues Found

### 1. ❌ Wrong Top-Bottom Endpoint (useAirlineData.ts:194)
**Current:**
```typescript
const response = await fetch(`${endpoint}/top-bottom`);
// If endpoint is /api/v1/airlines/stats
// Creates: /api/v1/airlines/stats/top-bottom ❌
```

**Should be:**
```typescript
const response = await fetch(`${API_BASE_URL}/api/v1/airlines/top-bottom`);
// Creates: /api/v1/airlines/top-bottom ✅
```

### 2. ⚠️ Trailing Slash (Index.tsx:43)
**Current:**
```typescript
const FLIGHTS_API_ENDPOINT = `${API_ENDPOINTS.FLIGHTS}/`;
// Creates: /api/v1/flights/ (trailing slash)
```

**Should be:**
```typescript
const FLIGHTS_API_ENDPOINT = API_ENDPOINTS.FLIGHTS;
// Creates: /api/v1/flights (no trailing slash)
```

### 3. ❌ Query Parameter Mismatch (Index.tsx:25-39)

**Frontend sends:**
- `destination` ✅ (matches backend)
- `date_range` ❌ (backend expects `date_from` and `date_to`)
- `day_of_week` ❌ (backend doesn't support this)
- `airline` ❌ (backend expects `airline_codes`)

**Backend expects:**
- `destination` ✅
- `date_from` (ISO datetime)
- `date_to` (ISO datetime)
- `airline_codes` (comma-separated codes like "LY,DL")
- `country`
- `min_flights`
- `min_on_time_percentage`
- `max_avg_delay`
- `sort_by`
- `sort_order`
- `limit`

## Fixes Needed

1. Fix top-bottom endpoint URL
2. Remove trailing slash from flights endpoint
3. Update query parameter building to match backend API
