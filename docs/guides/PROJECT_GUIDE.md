# Israel Flights ETL System - Complete Project Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [How It Works](#how-it-works)
4. [Prerequisites](#prerequisites)
5. [Setup Instructions](#setup-instructions)
6. [Running the System](#running-the-system)
7. [Accessing the Applications](#accessing-the-applications)
8. [Testing Tasks](#testing-tasks)
9. [Troubleshooting](#troubleshooting)
10. [Presentation Tips](#presentation-tips)

---

## Project Overview

The **Israel Flights ETL System** is a comprehensive end-to-end data pipeline that:
- **Extracts** real-time flight data from Israel's official government API (data.gov.il)
- **Transforms** the raw data (calculates delays, validates, cleans)
- **Loads** processed data into PostgreSQL database
- **Serves** data through a RESTful FastAPI backend
- **Visualizes** data in an interactive React dashboard

### Key Features
- **Automated ETL Pipeline**: Runs every 15 minutes via Apache Airflow
- **Data Storage**: Raw and processed data stored in AWS S3
- **RESTful API**: 15+ endpoints with advanced filtering and analytics
- **Interactive Dashboard**: Real-time flight data visualization with Hebrew/English support
- **Production-Ready**: Docker containerization, health checks, logging

---

## System Architecture

### High-Level Architecture

```
┌─────────────────┐
│   CKAN API      │  ← Data Source (data.gov.il)
│  (data.gov.il)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Apache Airflow │  ← ETL Orchestration (every 15 min)
│   (Scheduler)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│   S3   │ │PostgreSQL│  ← Data Storage
│ (Raw)  │ │(Processed)│
└────────┘ └────┬─────┘
                │
                ▼
         ┌──────────┐
         │ FastAPI  │  ← Backend API (Port 8000)
         │ Backend  │
         └────┬─────┘
              │
              ▼
         ┌──────────┐
         │  React    │  ← Frontend Dashboard (Port 3000)
         │ Frontend  │
         └──────────┘
```

### Component Details

#### 1. **Data Source Layer**
- **CKAN API** (data.gov.il)
- Resource ID: `e83f763b-b7d7-479e-b172-ae981ddc6de5`
- Provides real-time Israeli flight information
- RESTful API with pagination support

#### 2. **ETL Pipeline (Airflow)**
- **Scheduler**: Runs every 15 minutes (`*/15 * * * *`)
- **DAG**: `flight_data_pipeline`
- **Tasks**:
  1. `fetch_data` - Downloads data from CKAN API
  2. `validate_data` - Validates raw data
  3. `transform_data` - Transforms and calculates delays
  4. `load_to_db` - Loads data into PostgreSQL

#### 3. **Storage Layer**
- **AWS S3**: 
  - Raw data: `s3://etl-flight-pipeline-bucket/uploads/flights_data_YYYYMMDD_HHMMSS.json`
  - Processed data: `s3://etl-flight-pipeline-bucket/processed/flights_data_YYYYMMDD_HHMMSS.csv`
- **PostgreSQL**:
  - Database: `flights_db`
  - Table: `flights` (9,909+ records)
  - Port: 5433 (host), 5432 (container)

#### 4. **Backend API (FastAPI)**
- **Port**: 8000
- **Endpoints**: 15+ RESTful endpoints
- **Features**: Pagination, filtering, search, analytics
- **Documentation**: Auto-generated at `/docs`

#### 5. **Frontend Dashboard (React)**
- **Port**: 3000
- **Technology**: React + TypeScript + Tailwind CSS
- **Features**: 
  - Interactive data visualization
  - Multi-language (Hebrew/English)
  - Theme switching (Light/Dark)
  - Real-time filtering

---

## How It Works

### Data Flow

1. **Extraction** (Every 15 minutes)
   - Airflow scheduler triggers `fetch_data` task
   - Downloads flight data from CKAN API using pagination
   - Uploads raw JSON to S3 with timestamp
   - Saves local inspection copy

2. **Validation**
   - Checks if file exists in S3
   - Verifies file is not empty
   - Validates data structure

3. **Transformation**
   - Downloads JSON from S3
   - Calculates `delay_minutes` (actual_time - scheduled_time)
   - Cleans and validates data
   - Converts to CSV format
   - Uploads processed CSV to S3

4. **Loading**
   - Downloads processed CSV from S3
   - Computes unique `flight_id` (UUID based on natural keys)
   - Performs upsert operation (insert or update)
   - Handles duplicates with conflict resolution

5. **Serving**
   - FastAPI queries PostgreSQL
   - Returns paginated, filtered results
   - React frontend displays data with interactive UI

### Key Technologies

- **Airflow**: Workflow orchestration
- **PostgreSQL**: Relational database
- **AWS S3**: Object storage
- **FastAPI**: Python web framework
- **React**: Frontend framework
- **Docker**: Containerization

---

## Prerequisites

### Required Software

1. **Docker & Docker Compose**
   ```bash
   docker --version  # Should be 20.10+
   docker-compose --version  # Should be 1.29+
   ```

2. **Python 3.8+** (for local development)
   ```bash
   python3 --version
   ```

3. **Node.js 16+** (for frontend development)
   ```bash
   node --version
   npm --version
   ```

4. **AWS Account** (for S3 storage)
   - AWS Access Key ID
   - AWS Secret Access Key
   - AWS Default Region (e.g., `us-east-1`)

### Required AWS Resources

1. **S3 Bucket**: `etl-flight-pipeline-bucket`
   - Create bucket if it doesn't exist
   - Ensure proper IAM permissions

2. **IAM User** with S3 permissions:
   - `s3:PutObject`
   - `s3:GetObject`
   - `s3:ListBucket`

---

## Setup Instructions

### Step 1: Clone and Navigate

```bash
cd /Users/secondbite/Desktop/my_projects/israel-flights-etl
```

### Step 2: Configure Environment Variables

#### For Airflow (Required)

Create `airflow/.env` file:

```bash
cd airflow
touch .env
```

Add the following to `airflow/.env`:

```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_DEFAULT_REGION=us-east-1

# PostgreSQL Flights Database
POSTGRES_FLIGHTS_USER=daniel
POSTGRES_FLIGHTS_PASSWORD=daniel
```

**Important**: Replace `your_aws_access_key_id` and `your_aws_secret_access_key` with your actual AWS credentials.

#### For Backend (Optional - uses defaults)

The backend uses default values from `backend/app/config.py`. You can override with environment variables if needed.

### Step 3: Ensure PostgreSQL Flights Database Exists

The backend expects a PostgreSQL database named `flights_db` running on port `5433` (host) or `5432` (container).

The backend's `docker-compose.yaml` will create this automatically, but if running Airflow separately, ensure the database is accessible.

### Step 4: Verify Docker Volumes

The backend uses an external Docker volume. Ensure it exists:

```bash
docker volume inspect israel-flights-etl_postgres_flights_data
```

If it doesn't exist, the backend docker-compose will create it automatically.

---

## Running the System

### Option 1: Run Everything with Docker (Recommended)

#### 1. Start Backend Services (PostgreSQL + FastAPI)

```bash
cd backend
docker-compose up -d
```

**Wait for services to be healthy** (about 30-60 seconds):
```bash
docker-compose ps
# Should show "healthy" status
```

**Check logs**:
```bash
docker-compose logs -f backend
```

#### 2. Start Airflow Services

```bash
cd ../airflow
docker-compose up -d
```

**Wait for initialization** (about 2-3 minutes):
```bash
docker-compose logs -f airflow-init
# Wait for "Airflow initialization completed."
```

**Check services**:
```bash
docker-compose ps
# Should show: postgres, airflow-webserver, airflow-scheduler
```

#### 3. Start Frontend (Development Mode)

```bash
cd ../frontend
npm install  # Only needed first time
npm run dev
```

### Option 2: Run Locally (Development)

#### Backend (Local)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://daniel:daniel@localhost:5433/flights_db"

# Run
python -m app.main
```

#### Frontend (Local)

```bash
cd frontend
npm install
npm run dev
```

#### Airflow (Requires Docker)

Airflow must run in Docker due to its complex setup. Use Option 1 for Airflow.

---

## Accessing the Applications

Once all services are running:

### 1. Frontend Dashboard
- **URL**: http://localhost:3000
- **Features**: Interactive flight data visualization

### 2. Backend API
- **URL**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

### 3. Airflow UI
- **URL**: http://localhost:8082
- **Username**: `airflow`
- **Password**: `airflow`
- **DAG**: `flight_data_pipeline`

### 4. PostgreSQL Database
- **Host**: `localhost`
- **Port**: `5433` (from host), `5432` (from container)
- **Database**: `flights_db`
- **User**: `daniel`
- **Password**: `daniel`

**Connect via psql**:
```bash
psql -h localhost -p 5433 -U daniel -d flights_db
```

---

## Testing Tasks

Use these tasks to test each component of the system. Complete them in order to verify everything works.

### Phase 1: Infrastructure Testing

#### Task 1.1: Verify Docker Services
**Goal**: Ensure all Docker containers are running

**Steps**:
1. Check backend services:
   ```bash
   cd backend
   docker-compose ps
   ```
   - Should show: `backend`, `postgres_flights` (both "Up")

2. Check Airflow services:
   ```bash
   cd airflow
   docker-compose ps
   ```
   - Should show: `postgres_airflow`, `airflow-webserver`, `airflow-scheduler`

**Expected Result**: All services show "Up" status

---

#### Task 1.2: Test Database Connection
**Goal**: Verify PostgreSQL database is accessible

**Steps**:
1. Connect to database:
   ```bash
   psql -h localhost -p 5433 -U daniel -d flights_db
   ```

2. Check if `flights` table exists:
   ```sql
   \dt
   SELECT COUNT(*) FROM flights;
   \q
   ```

**Expected Result**: 
- Can connect to database
- `flights` table exists
- Table has records (may be 0 if ETL hasn't run yet)

---

#### Task 1.3: Test Backend Health
**Goal**: Verify FastAPI backend is running

**Steps**:
1. Check health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

2. Open API documentation:
   - Visit: http://localhost:8000/docs
   - Should see Swagger UI with all endpoints

**Expected Result**: 
- Health endpoint returns `200 OK`
- API docs page loads successfully

---

#### Task 1.4: Test Frontend
**Goal**: Verify React frontend is accessible

**Steps**:
1. Open browser: http://localhost:3000
2. Check browser console for errors (F12)
3. Verify page loads without errors

**Expected Result**: 
- Dashboard page loads
- No console errors
- UI is responsive

---

### Phase 2: ETL Pipeline Testing

#### Task 2.1: Access Airflow UI
**Goal**: Verify Airflow web interface

**Steps**:
1. Open: http://localhost:8082
2. Login:
   - Username: `airflow`
   - Password: `airflow`
3. Find DAG: `flight_data_pipeline`
4. Check DAG status (should be green/paused)

**Expected Result**: 
- Can login to Airflow
- DAG is visible
- DAG shows last run status

---

#### Task 2.2: Trigger Manual DAG Run
**Goal**: Test ETL pipeline execution

**Steps**:
1. In Airflow UI, find `flight_data_pipeline` DAG
2. Click "Play" button to trigger DAG
3. Click on DAG name to see task details
4. Monitor task execution:
   - `fetch_data` (green = success)
   - `validate_data` (green = success)
   - `transform_data` (green = success)
   - `load_to_db` (green = success)

**Expected Result**: 
- All tasks complete successfully (green)
- No failed tasks
- Check task logs for any warnings

---

#### Task 2.3: Verify S3 Upload
**Goal**: Confirm data is uploaded to S3

**Steps**:
1. Check Airflow logs for S3 path:
   ```bash
   cd airflow
   docker-compose logs airflow-scheduler | grep "s3://"
   ```

2. Or check AWS S3 console:
   - Bucket: `etl-flight-pipeline-bucket`
   - Path: `uploads/` (raw) and `processed/` (processed)

**Expected Result**: 
- Files exist in S3 bucket
- Raw JSON files in `uploads/`
- Processed CSV files in `processed/`

---

#### Task 2.4: Verify Database Load
**Goal**: Confirm data is loaded into PostgreSQL

**Steps**:
1. Connect to database:
   ```bash
   psql -h localhost -p 5433 -U daniel -d flights_db
   ```

2. Check record count:
   ```sql
   SELECT COUNT(*) FROM flights;
   ```

3. Check recent records:
   ```sql
   SELECT flight_id, airline_code, flight_number, scheduled_time 
   FROM flights 
   ORDER BY scrape_timestamp DESC 
   LIMIT 10;
   \q
   ```

**Expected Result**: 
- Record count > 0
- Recent records show current data
- All required columns have data

---

### Phase 3: Backend API Testing

#### Task 3.1: Test Basic Endpoints
**Goal**: Verify core API functionality

**Steps**:
1. Test health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

2. Test flights list (first page):
   ```bash
   curl "http://localhost:8000/api/v1/flights?page=1&size=5"
   ```

3. Test airlines endpoint:
   ```bash
   curl http://localhost:8000/api/v1/airlines
   ```

**Expected Result**: 
- All endpoints return `200 OK`
- JSON responses are valid
- Data structure matches expected schema

---

#### Task 3.2: Test Filtering
**Goal**: Verify filtering functionality

**Steps**:
1. Filter by airline:
   ```bash
   curl "http://localhost:8000/api/v1/flights?airline_code=LY&page=1&size=5"
   ```

2. Filter by direction:
   ```bash
   curl "http://localhost:8000/api/v1/flights?direction=D&page=1&size=5"
   ```

3. Filter by date range:
   ```bash
   curl "http://localhost:8000/api/v1/flights?date_from=2025-01-01&date_to=2025-01-31&page=1&size=5"
   ```

**Expected Result**: 
- Filters work correctly
- Results match filter criteria
- Pagination still works

---

#### Task 3.3: Test Search
**Goal**: Verify search functionality

**Steps**:
1. Search flights:
   ```bash
   curl "http://localhost:8000/api/v1/flights/search?q=Tel%20Aviv&page=1&size=5"
   ```

2. Search airlines:
   ```bash
   curl "http://localhost:8000/api/v1/airlines?search=El%20Al"
   ```

**Expected Result**: 
- Search returns relevant results
- Search is case-insensitive
- Results are properly formatted

---

#### Task 3.4: Test Analytics Endpoints
**Goal**: Verify analytics functionality

**Steps**:
1. Get airline statistics:
   ```bash
   curl "http://localhost:8000/api/v1/airlines/stats?min_flights=20"
   ```

2. Get flight statistics:
   ```bash
   curl "http://localhost:8000/api/v1/flights/stats?group_by=airline"
   ```

**Expected Result**: 
- Statistics are calculated correctly
- Aggregations are accurate
- Response includes expected metrics

---

#### Task 3.5: Test Pagination
**Goal**: Verify pagination works correctly

**Steps**:
1. Get first page:
   ```bash
   curl "http://localhost:8000/api/v1/flights?page=1&size=10"
   ```

2. Get second page:
   ```bash
   curl "http://localhost:8000/api/v1/flights?page=2&size=10"
   ```

3. Test max page size:
   ```bash
   curl "http://localhost:8000/api/v1/flights?page=1&size=200"
   ```

4. Test invalid page size:
   ```bash
   curl "http://localhost:8000/api/v1/flights?page=1&size=500"
   ```

**Expected Result**: 
- Pagination returns correct page
- Page size limits are enforced
- Invalid parameters return errors

---

### Phase 4: Frontend Testing

#### Task 4.1: Test Dashboard Load
**Goal**: Verify dashboard displays data

**Steps**:
1. Open: http://localhost:3000
2. Wait for data to load
3. Check if flight table displays data
4. Verify airline statistics tables show data

**Expected Result**: 
- Dashboard loads without errors
- Data is displayed in tables
- Loading states work correctly

---

#### Task 4.2: Test Filters
**Goal**: Verify frontend filtering

**Steps**:
1. Select an airline from filter dropdown
2. Select a date range
3. Select direction (Arrival/Departure)
4. Apply filters
5. Verify results update

**Expected Result**: 
- Filters update results correctly
- URL parameters update (if implemented)
- No errors in console

---

#### Task 4.3: Test Language Toggle
**Goal**: Verify multi-language support

**Steps**:
1. Click language toggle (Hebrew/English)
2. Verify UI text changes
3. Check if RTL layout works for Hebrew

**Expected Result**: 
- Language switches correctly
- All text is translated
- Layout adjusts for RTL

---

#### Task 4.4: Test Theme Toggle
**Goal**: Verify theme switching

**Steps**:
1. Click theme toggle (Light/Dark)
2. Verify colors change
3. Check if preference is saved

**Expected Result**: 
- Theme switches correctly
- All components update
- Preference persists

---

#### Task 4.5: Test Pagination
**Goal**: Verify frontend pagination

**Steps**:
1. Navigate to flights table
2. Click "Next" button
3. Click "Previous" button
4. Change page size
5. Verify data updates

**Expected Result**: 
- Pagination controls work
- Data updates correctly
- Page numbers are accurate

---

### Phase 5: Integration Testing

#### Task 5.1: End-to-End Data Flow
**Goal**: Verify complete data pipeline

**Steps**:
1. Trigger Airflow DAG manually
2. Wait for all tasks to complete
3. Check database for new records
4. Query API for new data
5. Verify frontend shows new data

**Expected Result**: 
- Data flows from API → S3 → Database → API → Frontend
- All steps complete successfully
- Data is consistent across layers

---

#### Task 5.2: Test Error Handling
**Goal**: Verify system handles errors gracefully

**Steps**:
1. Stop PostgreSQL container:
   ```bash
   cd backend
   docker-compose stop postgres_flights
   ```

2. Try to access API:
   ```bash
   curl http://localhost:8000/api/v1/flights
   ```

3. Restart PostgreSQL:
   ```bash
   docker-compose start postgres_flights
   ```

4. Verify API recovers

**Expected Result**: 
- API returns appropriate error
- System recovers when service restarts
- Error messages are user-friendly

---

#### Task 5.3: Test Performance
**Goal**: Verify system performance

**Steps**:
1. Measure API response time:
   ```bash
   time curl "http://localhost:8000/api/v1/flights?page=1&size=50"
   ```

2. Test with larger page size:
   ```bash
   time curl "http://localhost:8000/api/v1/flights?page=1&size=200"
   ```

3. Check database query performance:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM flights LIMIT 100;
   ```

**Expected Result**: 
- API responds in < 500ms for 50 items
- Database queries are optimized
- No performance degradation

---

## Troubleshooting

### Common Issues

#### Issue 1: Docker containers won't start
**Symptoms**: `docker-compose up` fails

**Solutions**:
- Check Docker is running: `docker ps`
- Check port conflicts: `lsof -i :8000`, `lsof -i :5433`
- Check disk space: `df -h`
- Review logs: `docker-compose logs`

---

#### Issue 2: Airflow DAG fails
**Symptoms**: Tasks show as failed (red) in Airflow UI

**Solutions**:
- Check task logs in Airflow UI
- Verify AWS credentials in `airflow/.env`
- Check S3 bucket exists and is accessible
- Verify PostgreSQL connection string
- Check Airflow logs: `docker-compose logs airflow-scheduler`

---

#### Issue 3: Backend can't connect to database
**Symptoms**: API returns 500 errors, health check fails

**Solutions**:
- Verify PostgreSQL is running: `docker-compose ps`
- Check database credentials in `backend/app/config.py`
- Test connection: `psql -h localhost -p 5433 -U daniel -d flights_db`
- Check backend logs: `docker-compose logs backend`

---

#### Issue 4: Frontend can't connect to API
**Symptoms**: Dashboard shows "Failed to fetch" or empty data

**Solutions**:
- Verify backend is running: `curl http://localhost:8000/health`
- Check CORS configuration in `backend/app/config.py`
- Check browser console for CORS errors
- Verify API URL in frontend code

---

#### Issue 5: No data in database
**Symptoms**: API returns empty results

**Solutions**:
- Check if ETL pipeline has run: Airflow UI
- Manually trigger DAG in Airflow
- Verify S3 has data files
- Check database: `SELECT COUNT(*) FROM flights;`
- Review ETL logs for errors

---

#### Issue 6: AWS S3 access denied
**Symptoms**: Airflow tasks fail with S3 permission errors

**Solutions**:
- Verify AWS credentials in `airflow/.env`
- Check IAM user has S3 permissions
- Verify bucket name: `etl-flight-pipeline-bucket`
- Test S3 access: `aws s3 ls s3://etl-flight-pipeline-bucket`

---

## Presentation Tips

### For Class Presentation

1. **Start with Overview** (2 minutes)
   - What the project does
   - Why it's useful
   - Key technologies used

2. **Show Architecture** (3 minutes)
   - Display architecture diagram
   - Explain data flow
   - Highlight key components

3. **Live Demo** (5 minutes)
   - Show Airflow UI with running DAG
   - Show backend API documentation
   - Show frontend dashboard with filters
   - Demonstrate language/theme toggle

4. **Technical Deep Dive** (5 minutes)
   - Explain ETL pipeline steps
   - Show code snippets (DAG, API endpoints)
   - Discuss data transformation logic

5. **Testing & Results** (3 minutes)
   - Show test results
   - Display data statistics
   - Highlight performance metrics

6. **Q&A** (2 minutes)
   - Be prepared for questions about:
     - Scalability
     - Error handling
     - Data quality
     - Future improvements

### Key Points to Emphasize

- **Automation**: ETL runs every 15 minutes automatically
- **Data Quality**: Validation and transformation ensure clean data
- **Scalability**: Docker containerization allows easy scaling
- **User Experience**: Multi-language, responsive design
- **Production-Ready**: Health checks, logging, error handling

### Demo Checklist

Before presentation, verify:
- [ ] All services are running
- [ ] Airflow DAG has recent successful run
- [ ] Database has data
- [ ] API endpoints work
- [ ] Frontend displays data correctly
- [ ] Filters work
- [ ] Language/theme toggles work

---

## Additional Resources

### Documentation Files
- `docs/services/SERVICES_SUMMARY.md` - Services/tools overview (what each service does)
- `docs/architecture/BACKEND_SYSTEM_DESIGN.md` - System architecture and design overview
- `docs/api/BACKEND_SPECIFICATION.md` - Complete backend API specification
- `docs/reference/FIELD_MAPPING_TABLE.md` - Source→target field mapping table
- `DEPLOYMENT.md` - EC2 deployment guide
- `README.md` - Quick start guide

### Useful Commands

**View logs**:
```bash
# Backend
cd backend && docker-compose logs -f backend

# Airflow
cd airflow && docker-compose logs -f airflow-scheduler

# All services
docker-compose logs -f
```

**Restart services**:
```bash
# Backend
cd backend && docker-compose restart

# Airflow
cd airflow && docker-compose restart
```

**Stop all services**:
```bash
cd backend && docker-compose down
cd ../airflow && docker-compose down
```

**Clean up (removes containers and volumes)**:
```bash
cd backend && docker-compose down -v
cd ../airflow && docker-compose down -v
```

Warning:
- `down -v` can delete your Postgres data if you are using Docker named volumes.
- To make flights data survive `down -v`, set `POSTGRES_FLIGHTS_DATA_DIR` in your `.env` to an absolute path (bind mount).
- If you intend to wipe everything, back up first (e.g., `pg_dump`) so you can restore.

---

## Summary

This project demonstrates a complete data engineering pipeline:
1. **ETL**: Automated data extraction, transformation, and loading
2. **Storage**: Multi-layer storage (S3 for raw, PostgreSQL for processed)
3. **API**: RESTful backend with advanced features
4. **UI**: Modern, interactive frontend dashboard

The system is production-ready with proper error handling, logging, and monitoring. Use the testing tasks to verify each component works correctly.

**Good luck with your presentation!** 🚀


