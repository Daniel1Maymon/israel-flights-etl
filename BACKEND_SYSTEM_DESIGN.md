# Israel Flights Backend - System Design Summary

> **ADHD-Friendly Guide**: Clear steps, visual flows, and bite-sized information

## Quick Overview (30 seconds)

The Cursor agent built a **modern FastAPI backend** with a **continuous ETL pipeline** that processes Israel flight data through a **layered architecture** with these key components:

- **ETL Pipeline** running every 15 minutes (Airflow + S3 + PostgreSQL)
- **15+ API Endpoints** for real-time flight data access and airline analytics
- **PostgreSQL Database** with continuously updated flight records
- **Advanced Airline Analytics** with KPI calculations and performance metrics
- **Production-Ready Features** (logging, error handling, health checks)
- **Sophisticated Filtering** (search, pagination, statistics, data quality scoring)

---

## System Architecture (The Big Picture)

```
┌─────────────────────────────────────┐
│           Frontend Layer            │  ← React Dashboard
│        (User Interface)             │
└─────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│            API Layer                │  ← FastAPI Application
│         (Request Processing)        │
│  • CORS Middleware                  │
│  • Error Handler                    │
│  • Request Logger                   │
└─────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│         Business Logic Layer        │  ← Core Services
│         (Data Processing)           │
│  • Flight Service                   │
│  • Airline Analytics Service        │
│  • Filter Engine                    │
│  • Search Engine                    │
│  • Statistics Engine                │
│  • KPI Calculation Engine           │
│  • Data Quality Assessment          │
└─────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│          Data Access Layer          │  ← Database Interface
│         (Query Processing)          │
│  • SQLAlchemy ORM                   │
│  • Query Builder                    │
│  • Session Management               │
└─────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│           Database Layer            │  ← Shared Data Storage
│    PostgreSQL (port 5432)           │
│  • flights table (9,909+ records)   │
│  • Indexed for Performance          │
│  • Connection Pooling               │
└─────────────────────────────────────┘
                   ▲
                   │
                   │
┌─────────────────────────────────────┐
│         ETL Pipeline Layer          │  ← Data Ingestion
│      (Runs Every 15 Minutes)        │
│  • Airflow Scheduler                │
│  • Extract: Israel Flights API      │
│  • Transform: Add delay calculations│
│  • Load: Upsert to SAME database    │
│  • S3: Raw & processed data storage │
└─────────────────────────────────────┘
```

---

## ETL Pipeline Flow (Data Ingestion Every 15 Minutes)

### Step 1: Extract (Every 15 Minutes)
```
1. Airflow Scheduler triggers at */15 * * * *
2. Fetch raw data from Israel Flights API (data.gov.il)
3. Download all records using pagination (1000 records/batch)
4. Upload raw JSON to S3: s3://bucket/raw/flights_data_YYYYMMDD_HHMMSS.json
5. Save local inspection copy for debugging
```

### Step 2: Validate
```
1. Check if S3 file exists and is not empty
2. Verify file integrity
3. Pass validated S3 path to next task
```

### Step 3: Transform
```
1. Download JSON from S3 to temporary file
2. Add delay_minutes calculation: actual_time - scheduled_time
3. Apply data cleaning and formatting
4. Convert to CSV format
5. Upload processed CSV to S3: s3://bucket/processed/flights_data_YYYYMMDD_HHMMSS.csv
6. Save local inspection copy
7. Clean up temporary files
```

### Step 4: Load
```
1. Download processed CSV from S3
2. Compute unique flight_id using natural keys (UUID)
3. Create flights table if not exists
4. Upsert data into PostgreSQL (handles duplicates)
5. Clean up temporary files
6. Log number of rows loaded
```

### ETL Schedule Details
```
Cron Expression: */15 * * * *
Frequency: Every 15 minutes
Start Time: 2025-01-01 (catchup=False)
Dependencies: fetch_data → validate_data → transform_data → load_to_db
Retry Policy: 1 retry with 5-minute delay
```

### Data Flow Between ETL and API
```
ETL Pipeline (Airflow)                    Backend API (FastAPI)
┌─────────────────────────┐              ┌─────────────────────────┐
│ 1. Fetches from API     │              │ 1. Receives HTTP request│
│ 2. Transforms data      │              │ 2. Queries database     │
│ 3. Upserts to PostgreSQL│ ────────────►│ 3. Returns JSON response│
│    (port 5432)          │              │    (same database)      │
└─────────────────────────┘              └─────────────────────────┘
         │                                        │
         ▼                                        ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│ PostgreSQL Database     │◄─────────────│ PostgreSQL Database     │
│ • flights table         │              │ • flights table         │
│ • Real-time updates     │              │ • Real-time reads       │
│ • Upsert operations     │              │ • SELECT queries        │
└─────────────────────────┘              └─────────────────────────┘
```

**Key Point**: Both ETL and API use the **same PostgreSQL database instance** (`postgres_flights` on port 5432). The ETL writes data, the API reads data. No data transfer between services - just shared database access.

---

## API Endpoints (What You Can Do)

### Step 1: Core Flight Operations
```
GET /api/v1/flights/           → List Flights (with pagination & filtering)
GET /api/v1/flights/{id}       → Single Flight (by ID)
GET /api/v1/flights/search     → Search Flights (text search)
GET /api/v1/flights/stats      → Flight Statistics (aggregated data)
GET /api/v1/flights/delays     → Delayed Flights (example endpoint)
```

### Step 2: Airline Analytics (NEW!)
```
GET /api/v1/airlines/stats     → Comprehensive Airline Performance KPIs
GET /api/v1/airlines/top-bottom → Top/Bottom Performing Airlines
GET /api/v1/airlines/destinations → Airline-Specific Destinations
GET /api/v1/airlines/{name}/destinations → Specific Airline Destinations
GET /api/v1/airlines/health    → Airline Service Health Check
```

### Step 3: Reference Data
```
GET /api/v1/airlines           → Airline List (unique airlines)
GET /api/v1/destinations       → Destination List (unique destinations)
GET /api/v1/flights/airlines   → Airline List (alternative endpoint)
GET /api/v1/flights/destinations → Destination List (alternative endpoint)
```

### Step 4: System Health
```
GET /                         → API Root Information
GET /health                   → Basic Health Check
GET /ready                    → Database Connectivity Check
GET /metrics                  → Performance Data
```

**Total: 15+ Endpoints** (expanded from original 6)

---

## Request Flow (Step-by-Step)

### Step 1: Request Arrives
```
1. Frontend sends: GET /api/v1/flights?page=1&size=50
2. FastAPI receives request
3. CORS middleware checks origin
4. Error handling middleware validates request
5. Routes to appropriate endpoint
```

### Step 2: Business Logic
```
1. Endpoint calls Flight Service
2. Service applies filters (direction, airline, etc.)
3. Filter Engine builds SQL query
4. Query executes against database
5. Database returns raw flight data
6. Service processes and formats data
7. Returns structured flight objects
```

### Step 3: Response
```
1. Endpoint converts to Pydantic schema
2. Pydantic validates and serializes data
3. JSON response sent to frontend
4. Frontend displays flight data to user
```

---

## Database Design (Data Structure)

### Step 1: Table Structure
```
Table: flights
├── flight_id (Primary Key) - string
├── airline_code - string
├── flight_number - string
├── direction - string (A=Arrival, D=Departure)
├── location_iata - string
├── location_en - string
├── location_he - string
├── location_city_en - string (NEW)
├── country_en - string (NEW)
├── country_he - string (NEW)
├── scheduled_time - timestamp
├── actual_time - timestamp
├── delay_minutes - integer
├── airline_name - string
├── status_en - string
├── status_he - string
├── terminal - string
├── checkin_counters - string (NEW)
├── checkin_zone - string (NEW)
├── scrape_timestamp - timestamp
└── raw_s3_path - string
```

### Step 2: Key Indexes (Performance)
```
flights table indexes:
├── Primary Key: flight_id
├── Index: airline_code (for airline filtering)
├── Index: direction (for arrival/departure filtering)
├── Index: scheduled_time (for date range queries)
├── Index: status_en (for status filtering)
├── Index: terminal (for terminal filtering)
└── Index: delay_minutes (for delay range queries)
```

---

## Airline Analytics System (NEW!)

### Step 1: AirlineAggregationService
```
The system now includes a sophisticated airline analytics service that:

• Calculates Key Performance Indicators (KPIs) for each airline
• Handles complex data aggregation and grouping
• Provides data quality scoring for reliability assessment
• Supports advanced filtering and sorting options
• Caches results for performance optimization
```

### Step 2: Key Performance Indicators (KPIs)
```
For each airline, the system calculates:

• On-Time Percentage: % of flights arriving/departing on time
• Average Delay: Mean delay time for delayed flights only
• Total Flights: Count of all flights for the airline
• Cancellation Rate: % of flights that were cancelled
• Data Quality Score: Reliability assessment (0-100)
• Destinations Served: List of unique destinations
• Last Updated: Timestamp of last calculation
```

### Step 3: Advanced Analytics Features
```
• Top/Bottom Analysis: Best and worst performing airlines
• Destination Performance: How airlines perform to specific destinations
• Data Quality Assessment: Identifies airlines with incomplete data
• Flexible Filtering: By date range, destination, country, airline codes
• Performance Sorting: By on-time %, delay time, flight count, etc.
• Caching: 15-minute cache for improved performance
```

### Step 4: API Response Example
```json
{
  "airlines": [
    {
      "airline_code": "LY",
      "airline_name": "El Al Israel Airlines",
      "on_time_percentage": 85.2,
      "avg_delay_minutes": 12.5,
      "total_flights": 1250,
      "cancellation_percentage": 2.1,
      "data_quality_score": 94.5,
      "destinations": ["New York", "London", "Paris"],
      "last_updated": "2024-01-15T10:30:00Z"
    }
  ],
  "total_airlines": 15,
  "total_flights": 9909,
  "calculation_time_ms": 245
}
```

---

## Filtering System (How Search Works)

### Step 1: Filter Types
```
Query Parameters → Filter Type Check:

IF direction filter → WHERE direction = 'D' (departure) or 'A' (arrival)
IF airline filter → WHERE airline_code = 'LY' (El Al)
IF status filter → WHERE status_en = 'On Time'
IF date range → WHERE scheduled_time BETWEEN start_date AND end_date
IF delay range → WHERE delay_minutes BETWEEN 10 AND 30
IF search query → WHERE column ILIKE '%search_term%'

All filters → Combined into single SQL query
```

### Step 2: Search Fields
```
Search Query searches across these fields:
├── airline_name (El Al Israel Airlines)
├── location_en (Ben Gurion Airport)
├── location_he (נמל התעופה בן גוריון)
├── location_city_en (Tel Aviv) (NEW)
├── country_en (Israel) (NEW)
├── country_he (ישראל) (NEW)
├── flight_number (LY001)
└── airline_code (LY)
```

---

## Pagination System (How Data is Split)

### Step 1: Pagination Logic
```
Request: page=2, size=50

1. Calculate offset: (page-1) × size = (2-1) × 50 = 50
2. Build query: LIMIT 50 OFFSET 50
3. Execute query: Returns records 51-100
4. Calculate total pages: (total_records + size - 1) ÷ size
5. Return pagination metadata with response
```

### Step 2: Response Format
```json
{
  "data": [...], // 50 flight records
  "pagination": {
    "page": 2,
    "size": 50,
    "total": 9909,
    "pages": 199,
    "has_next": true,
    "has_prev": true
  }
}
```

---

## Error Handling (What Goes Wrong)

### Step 1: Error Types
```
Request comes in:

IF request is invalid → 400 Bad Request
IF database is down → 500 Server Error
IF resource not found → 404 Not Found
IF query validation fails → 422 Validation Error
IF everything is OK → 200 Success

Each error includes helpful message and details
```

### Step 2: Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {"field": "page", "issue": "Must be positive integer"}
  }
}
```

---

## Logging System (What Gets Tracked)

### Step 1: Log Types
```
Application Logs:
├── Request Logs
│   └── Method, URL, Client IP, Response Time
├── Error Logs
│   └── Error Message, Stack Trace, Context
├── Database Logs
│   └── Query Time, Connection Status, Errors
└── Performance Logs
    └── Response Time, Memory Usage, CPU Usage
```

### Step 2: Log Format (JSON)
```json
{
  "timestamp": "2024-01-15T08:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "method": "GET",
  "url": "/api/v1/flights",
  "status_code": 200,
  "process_time": 0.125
}
```

---

## Deployment Architecture (Production Ready)

### Step 1: Container Setup
```
Docker Container:
├── FastAPI App (Port 8000)
├── Python 3.11 (Optimized)
├── Uvicorn Server (Async Support)
└── Health Checks (/health, /ready, /metrics)
```

### Step 2: Environment Configuration
```
Development Environment:
├── Database: localhost:5433
└── Credentials: daniel:daniel

Staging Environment:
├── Database: staging-db:5432
└── Credentials: staging-user:staging-pass

Production Environment:
├── Database: prod-db:5432
└── Credentials: prod-user:secure-pass
```

---

## Project Structure (File Organization)

### Step 1: Directory Layout
```
backend/
├── app/                    # Main application
│   ├── api/               # API endpoints
│   │   ├── v1/            # API version 1
│   │   │   └── flights.py # Flight endpoints
│   │   └── airline_endpoints.py # Airline analytics endpoints (NEW)
│   ├── models/            # Database models
│   │   └── flight.py      # Flight model
│   ├── schemas/           # Pydantic schemas
│   │   ├── flight.py      # Request/response schemas
│   │   └── airline.py     # Airline analytics schemas (NEW)
│   ├── services/          # Business logic services (NEW)
│   │   └── airline_aggregation.py # Airline analytics service
│   ├── utils/             # Utility functions
│   │   └── filters.py     # Filtering utilities
│   ├── main.py            # FastAPI app setup
│   ├── config.py          # Configuration
│   └── database.py        # Database connection
├── requirements.txt       # Dependencies
├── Dockerfile            # Container config
└── docker-compose.yaml   # Multi-service setup
```

### Step 2: Key Files Purpose
```
main.py → FastAPI App Setup
config.py → Environment Settings
database.py → DB Connection Pool
flights.py → Core Flight API Endpoints
airline_endpoints.py → Airline Analytics Endpoints (NEW)
airline_aggregation.py → Airline KPI Calculation Service (NEW)
filters.py → Query Building
flight.py (models) → Database Schema
flight.py (schemas) → Flight Data Validation
airline.py (schemas) → Airline Analytics Data Validation (NEW)
```

---

## Testing Strategy (Quality Assurance)

### Step 1: Test Types
```
Testing Strategy:
├── Manual Testing
│   ├── Core Functionality
│   ├── Filtering Tests
│   └── Error Handling
└── Automated Testing
    └── test_basic.py
        ├── Health Check Tests
        ├── API Endpoint Tests
        └── Database Tests
```

### Step 2: Test Checklist
- [ ] **Health Check**: `GET /health` returns 200
- [ ] **List Flights**: `GET /api/v1/flights` returns data
- [ ] **Single Flight**: `GET /api/v1/flights/{id}` works
- [ ] **Search**: `GET /api/v1/flights/search?q=test` works
- [ ] **Filtering**: All filter parameters work
- [ ] **Airline Analytics**: `GET /api/v1/airlines/stats` returns KPIs
- [ ] **Top/Bottom Airlines**: `GET /api/v1/airlines/top-bottom` works
- [ ] **Airline Destinations**: `GET /api/v1/airlines/destinations` works
- [ ] **Data Quality**: Airline data quality scores are calculated
- [ ] **Error Handling**: Invalid requests return proper errors

---

## Performance Features (Speed & Efficiency)

### Step 1: Database Optimizations
```
Performance Optimizations:
├── Connection Pooling
│   ├── 10 Base Connections
│   └── 20 Max Overflow
├── Query Optimization
│   └── Parameterized Queries (SQL injection safe)
└── Indexing Strategy
    └── Strategic Indexes on frequently queried fields
```

### Step 2: API Performance
```
Request → Pagination → Max 200 items/page → Efficient Serialization → Fast JSON Response
```

---

## Security Features (Protection)

### Step 1: Security Layers
```
Security Features:
├── Input Validation
│   └── Pydantic Validation (type checking)
├── SQL Injection Prevention
│   └── Parameterized Queries only
├── Pagination Limits
│   └── ALL endpoints have max 200 items/page limit
├── Data Exposure Prevention
│   └── No endpoints return ALL records without pagination
├── CORS Configuration
│   └── Allowed Origins Only
└── Error Sanitization
    └── No Sensitive Data in Error Messages
```

---

## Key Takeaways (What You Need to Remember)

### What Works Well
1. **Clean Architecture**: Easy to understand and maintain
2. **Production Ready**: Logging, error handling, health checks
3. **Scalable**: Connection pooling, efficient queries
4. **Advanced Analytics**: Sophisticated airline performance analysis
5. **Data Quality**: Built-in data quality assessment and scoring
6. **Well Documented**: Auto-generated API docs
7. **Type Safe**: Pydantic schemas prevent errors
8. **Performance Optimized**: Caching and efficient aggregation queries

### How to Use
1. **Start**: `python -m app.main`
2. **Test**: `curl http://localhost:8000/health`
3. **Explore**: Visit `http://localhost:8000/docs`
4. **Query Flights**: Use filters and pagination
5. **Analyze Airlines**: Use `/api/v1/airlines/stats` for KPIs
6. **Monitor**: Check logs and metrics

### Next Steps
1. **Add Authentication**: JWT tokens for production
2. **Implement Caching**: Redis for better performance
3. **Add Rate Limiting**: Prevent API abuse
4. **Deploy to Cloud**: AWS/Azure/GCP setup
5. **Add Monitoring**: Prometheus + Grafana

---

## Quick Start Commands

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export DATABASE_URL="postgresql://daniel:daniel@localhost:5432/flights_db"

# 5. Start the server
python -m app.main

# 6. Test the API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/flights?page=1&size=5

# 7. Test airline analytics
curl http://localhost:8000/api/v1/airlines/stats
curl http://localhost:8000/api/v1/airlines/top-bottom

# 8. View documentation
open http://localhost:8000/docs
```

---

**That's it!** The Cursor agent built a professional-grade backend that's ready for production use. The system is well-architected, thoroughly documented, and includes advanced airline analytics capabilities that go far beyond basic CRUD operations. The system now provides sophisticated data analysis, performance metrics, and data quality assessment - making it a comprehensive flight data platform.
