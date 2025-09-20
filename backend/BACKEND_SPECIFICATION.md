# FastAPI Backend Implementation Specification

## Overview
This document serves as a comprehensive specification for the FastAPI backend implementation for the Israel Flights ETL project. Use this to verify that all requirements are met during implementation.

## Database Connection

### Development
- **Host**: localhost
- **Port**: 5433
- **Database**: flights_db
- **Username**: daniel
- **Password**: daniel
- **Connection Pool**: Minimum 5, Maximum 20 connections

### Production
- **Host**: Environment variable `DB_HOST`
- **Port**: Environment variable `DB_PORT` (default: 5432)
- **Database**: Environment variable `DB_NAME`
- **Username**: Environment variable `DB_USER`
- **Password**: Environment variable `DB_PASSWORD` (from secure secret store)
- **Connection Pool**: Minimum 10, Maximum 50 connections
- **SSL**: Required in production (`sslmode=require`)
- **Connection Timeout**: 30 seconds
- **Query Timeout**: 60 seconds

## API Endpoints Specification

### Base URL
- Development: `http://localhost:8000`
- Staging: `https://api-staging.flights.example.com`
- Production: `https://api.flights.example.com`
- API Version: `/api/v1`

### 1. List Flights
- **Endpoint**: `GET /api/v1/flights`
- **Purpose**: Retrieve paginated list of flights
- **Query Parameters**:
  - `page` (int, optional): Page number (default: 1)
  - `size` (int, optional): Items per page (default: 50, max: 200)
  - `direction` (str, optional): Filter by direction ('A' for arrival, 'D' for departure)
  - `airline_code` (str, optional): Filter by airline code (e.g., 'LY', 'UA')
  - `status` (str, optional): Filter by status (e.g., 'On Time', 'Boarding', 'Landed')
  - `terminal` (str, optional): Filter by terminal number
  - `date_from` (str, optional): Filter flights from date (ISO format)
  - `date_to` (str, optional): Filter flights to date (ISO format)
  - `delay_min` (int, optional): Minimum delay in minutes
  - `delay_max` (int, optional): Maximum delay in minutes

### 2. Get Single Flight
- **Endpoint**: `GET /api/v1/flights/{flight_id}`
- **Purpose**: Retrieve specific flight by ID
- **Path Parameters**:
  - `flight_id` (str): Unique flight identifier

### 3. Search Flights
- **Endpoint**: `GET /api/v1/flights/search`
- **Purpose**: Search flights by various criteria
- **Query Parameters**:
  - `q` (str, required): Search query
  - `search_fields` (str, optional): Comma-separated fields to search in
  - All pagination and filter parameters from list endpoint

### 4. Flight Statistics
- **Endpoint**: `GET /api/v1/flights/stats`
- **Purpose**: Get aggregated flight statistics
- **Query Parameters**:
  - `date_from` (str, optional): Start date for statistics
  - `date_to` (str, optional): End date for statistics
  - `group_by` (str, optional): Group by field ('airline', 'destination', 'hour', 'day')

### 5. List Airlines
- **Endpoint**: `GET /api/v1/airlines`
- **Purpose**: Get list of unique airlines
- **Query Parameters**:
  - `search` (str, optional): Search airline names

### 6. List Destinations
- **Endpoint**: `GET /api/v1/destinations`
- **Purpose**: Get list of unique destinations
- **Query Parameters**:
  - `search` (str, optional): Search destination names
  - `country` (str, optional): Filter by country

## API Documentation Examples

### Example 1: List Flights (Basic)
```bash
curl -X GET "http://localhost:8000/api/v1/flights?page=1&size=10"
```

**Response:**
```json
{
  "data": [
    {
      "flight_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
      "airline_code": "LY",
      "flight_number": "LY001",
      "direction": "D",
      "location_iata": "TLV",
      "scheduled_time": "2024-01-15T08:30:00Z",
      "actual_time": "2024-01-15T08:45:00Z",
      "airline_name": "El Al Israel Airlines",
      "location_en": "Ben Gurion Airport",
      "location_he": "נמל התעופה בן גוריון",
      "location_city_en": "Tel Aviv",
      "country_en": "Israel",
      "country_he": "ישראל",
      "terminal": "3",
      "checkin_counters": "1-12",
      "checkin_zone": "A",
      "status_en": "Boarding",
      "status_he": "עלייה למטוס",
      "delay_minutes": 15,
      "scrape_timestamp": "2024-01-15T08:00:00Z",
      "raw_s3_path": "s3://flight-data/raw/2024/01/15/ly001_tlv_0830.json"
    }
  ],
  "pagination": {
    "page": 1,
    "size": 10,
    "total": 9909,
    "pages": 991,
    "has_next": true,
    "has_prev": false
  }
}
```

### Example 2: Filter Flights by Airline
```bash
curl -X GET "http://localhost:8000/api/v1/flights?airline_code=LY&direction=D&page=1&size=5"
```

### Example 3: Search Flights
```bash
curl -X GET "http://localhost:8000/api/v1/flights/search?q=Tel%20Aviv&page=1&size=10"
```

### Example 4: Get Single Flight
```bash
curl -X GET "http://localhost:8000/api/v1/flights/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

**Response:**
```json
{
  "flight_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "airline_code": "LY",
  "flight_number": "LY001",
  "direction": "D",
  "location_iata": "TLV",
  "scheduled_time": "2024-01-15T08:30:00Z",
  "actual_time": "2024-01-15T08:45:00Z",
  "airline_name": "El Al Israel Airlines",
  "location_en": "Ben Gurion Airport",
  "location_he": "נמל התעופה בן גוריון",
  "location_city_en": "Tel Aviv",
  "country_en": "Israel",
  "country_he": "ישראל",
  "terminal": "3",
  "checkin_counters": "1-12",
  "checkin_zone": "A",
  "status_en": "Boarding",
  "status_he": "עלייה למטוס",
  "delay_minutes": 15,
  "scrape_timestamp": "2024-01-15T08:00:00Z",
  "raw_s3_path": "s3://flight-data/raw/2024/01/15/ly001_tlv_0830.json"
}
```

### Example 5: Get Flight Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/flights/stats?group_by=airline&date_from=2024-01-01&date_to=2024-01-31"
```

**Response:**
```json
{
  "total_flights": 1500,
  "on_time_flights": 1200,
  "delayed_flights": 300,
  "average_delay": 12.5,
  "by_airline": [
    {
      "airline_code": "LY",
      "airline_name": "El Al Israel Airlines",
      "total_flights": 800,
      "on_time_percentage": 85.5,
      "average_delay": 8.2
    }
  ]
}
```

### Example 6: List Airlines
```bash
curl -X GET "http://localhost:8000/api/v1/airlines?search=El%20Al"
```

**Response:**
```json
[
  {
    "airline_code": "LY",
    "airline_name": "El Al Israel Airlines",
    "flight_count": 800
  }
]
```

## Environment Setup Instructions

### Prerequisites
- Python 3.8+
- PostgreSQL running on localhost:5433
- Database `flights_db` with `flights` table populated

### Quick Start (5 minutes)

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables:**
   ```bash
   export DATABASE_URL="postgresql://daniel:daniel@localhost:5433/flights_db"
   export CORS_ORIGINS="http://localhost:3000"
   ```

5. **Run the application:**
   ```bash
   python -m app.main
   ```

6. **Test the API:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/flights?page=1&size=5
   ```

7. **View API documentation:**
   - Open http://localhost:8000/docs in your browser
   - Interactive Swagger UI with all endpoints

### Docker Setup (Alternative)
```bash
cd backend
docker-compose up -d
```

## Basic Testing Strategy

### Manual Testing Checklist

#### Core Functionality Tests
- [ ] **Health Check**: `GET /health` returns 200 OK
- [ ] **List Flights**: `GET /api/v1/flights` returns paginated data
- [ ] **Single Flight**: `GET /api/v1/flights/{id}` returns specific flight
- [ ] **Search**: `GET /api/v1/flights/search?q=test` returns filtered results
- [ ] **Airlines**: `GET /api/v1/airlines` returns airline list
- [ ] **Destinations**: `GET /api/v1/destinations` returns destination list

#### Filtering Tests
- [ ] **Direction Filter**: `?direction=D` returns only departures
- [ ] **Airline Filter**: `?airline_code=LY` returns only El Al flights
- [ ] **Status Filter**: `?status=On%20Time` returns only on-time flights
- [ ] **Date Range**: `?date_from=2024-01-01&date_to=2024-01-31` returns date range
- [ ] **Delay Filter**: `?delay_min=10` returns flights with 10+ minute delays

#### Pagination Tests
- [ ] **Page 1**: `?page=1&size=10` returns first 10 items
- [ ] **Page 2**: `?page=2&size=10` returns next 10 items
- [ ] **Large Page**: `?size=200` returns up to 200 items
- [ ] **Invalid Page**: `?page=0` returns error 400
- [ ] **Oversized Page**: `?size=500` returns error 400

#### Error Handling Tests
- [ ] **Invalid Flight ID**: `GET /api/v1/flights/invalid` returns 404
- [ ] **Invalid Parameters**: `?page=abc` returns 422
- [ ] **Database Down**: Returns 500 when DB unavailable
- [ ] **CORS**: Frontend can make requests from localhost:3000

### Automated Testing (MVP Level)
```python
# test_basic.py - Run these tests
import requests

def test_health_check():
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200

def test_list_flights():
    response = requests.get("http://localhost:8000/api/v1/flights?page=1&size=5")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "pagination" in data
    assert len(data["data"]) <= 5

def test_single_flight():
    # First get a flight ID
    response = requests.get("http://localhost:8000/api/v1/flights?page=1&size=1")
    flight_id = response.json()["data"][0]["flight_id"]
    
    # Then get that specific flight
    response = requests.get(f"http://localhost:8000/api/v1/flights/{flight_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["flight_id"] == flight_id

def test_search():
    response = requests.get("http://localhost:8000/api/v1/flights/search?q=LY")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data

def test_filtering():
    response = requests.get("http://localhost:8000/api/v1/flights?direction=D&airline_code=LY")
    assert response.status_code == 200
    data = response.json()
    for flight in data["data"]:
        assert flight["direction"] == "D"
        assert flight["airline_code"] == "LY"
```

## Response Format Specifications

### Flight Object Schema
```json
{
  "flight_id": "string",
  "airline_code": "string",
  "flight_number": "string",
  "direction": "string", // 'A' or 'D'
  "location_iata": "string",
  "scheduled_time": "string", // ISO 8601 format
  "actual_time": "string", // ISO 8601 format
  "airline_name": "string",
  "location_en": "string",
  "location_he": "string",
  "location_city_en": "string",
  "country_en": "string",
  "country_he": "string",
  "terminal": "string",
  "checkin_counters": "string",
  "checkin_zone": "string",
  "status_en": "string",
  "status_he": "string",
  "delay_minutes": "integer",
  "scrape_timestamp": "string", // ISO 8601 format
  "raw_s3_path": "string"
}
```

### Paginated Response Schema
```json
{
  "data": [Flight],
  "pagination": {
    "page": "integer",
    "size": "integer",
    "total": "integer",
    "pages": "integer",
    "has_next": "boolean",
    "has_prev": "boolean"
  }
}
```

### Error Response Schema
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object" // optional
  }
}
```

## Database Schema Mapping

### PostgreSQL Table: `flights`
| Column | Type | API Field | Description |
|--------|------|-----------|-------------|
| flight_id | VARCHAR(32) | flight_id | Primary key |
| airline_code | VARCHAR(10) | airline_code | IATA airline code |
| flight_number | VARCHAR(20) | flight_number | Flight number |
| direction | VARCHAR(1) | direction | A=Arrival, D=Departure |
| location_iata | VARCHAR(10) | location_iata | Airport IATA code |
| scheduled_time | TIMESTAMP | scheduled_time | Scheduled departure/arrival |
| actual_time | TIMESTAMP | actual_time | Actual departure/arrival |
| airline_name | VARCHAR(100) | airline_name | Full airline name |
| location_en | VARCHAR(100) | location_en | Airport name (English) |
| location_he | VARCHAR(100) | location_he | Airport name (Hebrew) |
| location_city_en | VARCHAR(100) | location_city_en | City name (English) |
| country_en | VARCHAR(100) | country_en | Country name (English) |
| country_he | VARCHAR(100) | country_he | Country name (Hebrew) |
| terminal | VARCHAR(10) | terminal | Terminal number |
| checkin_counters | VARCHAR(100) | checkin_counters | Check-in counter info |
| checkin_zone | VARCHAR(100) | checkin_zone | Check-in zone |
| status_en | VARCHAR(100) | status_en | Status (English) |
| status_he | VARCHAR(100) | status_he | Status (Hebrew) |
| delay_minutes | INTEGER | delay_minutes | Delay in minutes |
| scrape_timestamp | TIMESTAMP | scrape_timestamp | Data collection time |
| raw_s3_path | VARCHAR(500) | raw_s3_path | S3 path to raw data |

## Error Handling Requirements

### HTTP Status Codes
- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

### Error Scenarios
1. **Invalid flight_id**: Return 404 with error message
2. **Invalid query parameters**: Return 400 with validation details
3. **Database connection error**: Return 500 with generic error message
4. **Invalid pagination**: Return 400 with pagination limits
5. **Search query too short**: Return 400 with minimum length requirement

## Performance Requirements

### Response Times
- List flights (50 items): < 200ms
- Single flight lookup: < 100ms
- Search queries: < 500ms
- Statistics endpoint: < 1000ms

### Pagination Limits
- Default page size: 50
- Maximum page size: 200
- Maximum total results: 10,000 (for performance)

### Caching
- Flight statistics: Cache for 5 minutes
- Airline/destination lists: Cache for 1 hour
- Individual flights: No caching (real-time data)

## CORS Configuration
- **Allowed Origins**: `http://localhost:3000` (React dev server)
- **Allowed Methods**: `GET, POST, OPTIONS`
- **Allowed Headers**: `Content-Type, Authorization`
- **Credentials**: `false`

## Environment Variables

### Development
```bash
# Database
DATABASE_URL=postgresql://daniel:daniel@localhost:5433/flights_db
DB_HOST=localhost
DB_PORT=5433
DB_NAME=flights_db
DB_USER=daniel
DB_PASSWORD=daniel

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_TITLE="Israel Flights API"
API_VERSION=1.0.0
API_DESCRIPTION="API for Israeli flight data from ETL pipeline"

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Pagination
DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=200

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Production
```bash
# Database (from secret store)
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}  # From AWS Secrets Manager/Azure Key Vault

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_TITLE="Israel Flights API"
API_VERSION=1.0.0
API_DESCRIPTION="Production API for Israeli flight data"

# CORS (restrictive for production)
CORS_ORIGINS=https://flights.example.com,https://www.flights.example.com

# Logging
LOG_LEVEL=WARNING
LOG_FORMAT=json

# Pagination
DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=200

# Security
SECRET_KEY=${SECRET_KEY}  # From secret store
ACCESS_TOKEN_EXPIRE_MINUTES=15

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=20

# Monitoring
SENTRY_DSN=${SENTRY_DSN}
PROMETHEUS_ENABLED=true
HEALTH_CHECK_TIMEOUT=30

# Caching
REDIS_URL=redis://redis:6379/0
CACHE_TTL_SECONDS=300

# Performance
WORKERS=4
MAX_CONNECTIONS=100
KEEP_ALIVE_TIMEOUT=5
```

## Health Check Endpoints
- **Health**: `GET /health` - Basic health check
- **Ready**: `GET /ready` - Database connectivity check
- **Metrics**: `GET /metrics` - Basic performance metrics

## Implementation Checklist

### Core Setup
- [ ] FastAPI application initialization
- [ ] Database connection setup with SQLAlchemy
- [ ] Environment configuration management
- [ ] CORS middleware configuration
- [ ] Error handling middleware

### Models & Schemas
- [ ] SQLAlchemy Flight model
- [ ] Pydantic request/response schemas
- [ ] Database session management
- [ ] Model validation

### API Endpoints
- [ ] List flights endpoint with pagination
- [ ] Get single flight endpoint
- [ ] Search flights endpoint
- [ ] Flight statistics endpoint
- [ ] List airlines endpoint
- [ ] List destinations endpoint

### Features
- [ ] Pagination implementation
- [ ] Filtering by all specified criteria
- [ ] Search functionality across multiple fields
- [ ] Sorting capabilities
- [ ] Error handling for all scenarios
- [ ] Input validation

### Testing & Documentation
- [ ] Automatic OpenAPI documentation
- [ ] Health check endpoints
- [ ] Basic error handling tests
- [ ] Integration with existing database

### Deployment
- [ ] Docker configuration
- [ ] Requirements.txt with all dependencies
- [ ] Environment variable documentation
- [ ] Production-ready configuration

## Production Security Requirements

### Authentication & Authorization
- **API Keys**: Required for production endpoints (optional for development)
- **Rate Limiting**: 100 requests/minute per IP, 20 burst
- **Input Validation**: All inputs sanitized and validated
- **SQL Injection Prevention**: Parameterized queries only
- **XSS Protection**: Content-Type headers properly set
- **CSRF Protection**: CSRF tokens for state-changing operations

### Data Protection
- **PII Handling**: No personal data in logs or error messages
- **Data Encryption**: TLS 1.3 for all communications
- **Database Encryption**: At-rest encryption enabled
- **Secret Management**: All secrets in secure vault (AWS Secrets Manager/Azure Key Vault)
- **Audit Logging**: All API access logged with timestamps and IPs

### Network Security
- **HTTPS Only**: All production traffic over HTTPS
- **CORS Restrictions**: Only allowlisted origins
- **Security Headers**: HSTS, X-Frame-Options, X-Content-Type-Options
- **IP Whitelisting**: Optional for high-security environments

## Production Monitoring & Observability

### Health Checks
- **Liveness Probe**: `GET /health` - Application is running
- **Readiness Probe**: `GET /ready` - Application can serve traffic
- **Database Health**: Connection pool status and query performance
- **Dependency Health**: External service availability

### Metrics Collection
- **Prometheus Metrics**: Request count, duration, error rates
- **Custom Metrics**: Database query time, cache hit rate
- **Business Metrics**: Flight search frequency, popular routes
- **Infrastructure Metrics**: CPU, memory, disk usage

### Logging Strategy
- **Structured Logging**: JSON format for all logs
- **Log Levels**: ERROR, WARNING, INFO, DEBUG
- **Request Tracing**: Unique request IDs for tracing
- **Error Tracking**: Sentry integration for error monitoring
- **Log Aggregation**: Centralized logging (ELK stack/CloudWatch)

### Alerting
- **Error Rate**: Alert if error rate > 5%
- **Response Time**: Alert if p95 > 500ms
- **Database**: Alert on connection failures
- **Memory Usage**: Alert if memory > 80%
- **Disk Space**: Alert if disk > 85%

## Production Deployment

### Container Strategy
- **Base Image**: Python 3.11-slim (security updates)
- **Multi-stage Build**: Separate build and runtime stages
- **Non-root User**: Run as non-privileged user
- **Resource Limits**: CPU and memory limits set
- **Health Checks**: Container health check configured

### Infrastructure Requirements
- **Load Balancer**: Application load balancer with SSL termination
- **Auto Scaling**: Horizontal pod autoscaling based on CPU/memory
- **Database**: Managed PostgreSQL with read replicas
- **Caching**: Redis cluster for session and data caching
- **CDN**: CloudFront/CloudFlare for static content

### Deployment Pipeline
- **CI/CD**: GitHub Actions/GitLab CI
- **Testing**: Unit, integration, and load tests
- **Security Scanning**: SAST/DAST security scans
- **Blue-Green Deployment**: Zero-downtime deployments
- **Rollback Strategy**: Automated rollback on health check failures

### Environment Management
- **Development**: Local development with Docker Compose
- **Staging**: Production-like environment for testing
- **Production**: High-availability production environment
- **Feature Flags**: Toggle features without deployment

## Operational Procedures

### Backup & Recovery
- **Database Backups**: Daily automated backups with 30-day retention
- **Point-in-time Recovery**: 7-day point-in-time recovery capability
- **Disaster Recovery**: Multi-region backup strategy
- **Recovery Testing**: Monthly recovery procedure testing

### Maintenance Windows
- **Scheduled Maintenance**: Monthly maintenance windows
- **Security Updates**: Critical updates applied within 24 hours
- **Database Maintenance**: Quarterly database optimization
- **Monitoring**: 24/7 monitoring with on-call rotation

### Performance Optimization
- **Database Indexing**: Optimized indexes for common queries
- **Query Optimization**: Regular query performance analysis
- **Caching Strategy**: Multi-level caching (application, database, CDN)
- **Connection Pooling**: Optimized database connection pooling

### Capacity Planning
- **Load Testing**: Regular load testing with realistic traffic
- **Scaling Triggers**: Auto-scaling based on metrics
- **Resource Monitoring**: Continuous resource usage monitoring
- **Growth Projections**: Quarterly capacity planning reviews

## Success Criteria

### Functional Requirements
1. All endpoints return expected data format
2. Pagination works correctly with specified limits
3. All filters and search functionality work
4. Error handling returns appropriate HTTP status codes
5. CORS allows frontend integration
6. Response times meet performance requirements
7. Database queries are optimized
8. API documentation is automatically generated
9. Health checks confirm system status
10. Integration with existing PostgreSQL data works seamlessly

### Production Requirements
11. **Security**: All security requirements implemented and tested
12. **Monitoring**: Full observability with metrics, logs, and alerts
13. **Performance**: Handles expected load with <200ms response times
14. **Reliability**: 99.9% uptime with proper error handling
15. **Scalability**: Auto-scales to handle traffic spikes
16. **Maintainability**: Clean code with comprehensive documentation
17. **Compliance**: Meets data protection and security standards
18. **Disaster Recovery**: Backup and recovery procedures tested
19. **Operational Excellence**: Monitoring and alerting configured
20. **Documentation**: Complete operational runbooks and procedures
