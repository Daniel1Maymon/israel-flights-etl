# Services Summary - Israel Flights ETL System

This document provides a comprehensive overview of all services, tools, and technologies used in the project, along with the purpose of each.

---

## Table of Contents

1. [External Data Services](#external-data-services)
2. [Orchestration Services](#orchestration-services)
3. [Storage Services](#storage-services)
4. [Backend Services](#backend-services)
5. [Frontend Services](#frontend-services)
6. [Infrastructure Services](#infrastructure-services)
7. [Development Tools](#development-tools)

---

## External Data Services

### 1. CKAN API (data.gov.il)
**Type**: External REST API  
**Purpose**: Primary data source for Israeli flight information

**Details**:
- **URL**: `https://data.gov.il/api/3/action/datastore_search`
- **Resource ID**: `e83f763b-b7d7-479e-b172-ae981ddc6de5`
- **Data Format**: JSON with pagination support
- **Update Frequency**: Real-time (government-maintained)
- **Authentication**: None (public API)

**Why We Use It**:
- Official source of Israeli flight data
- Provides real-time flight information (arrivals/departures)
- Free and publicly accessible
- Reliable government infrastructure

**How It's Used**:
- Airflow DAG calls this API every 15 minutes
- Downloads all flight records using pagination (1000 records per batch)
- Data includes: airline codes, flight numbers, scheduled/actual times, terminals, status, etc.

---

## Orchestration Services

### 2. Apache Airflow
**Type**: Workflow orchestration platform  
**Purpose**: Automates and schedules the ETL pipeline

**Details**:
- **Version**: 3.0.4
- **Port**: 8082 (web UI)
- **Schedule**: Every 15 minutes (`*/15 * * * *`)
- **DAG Name**: `flight_data_pipeline`
- **Executor**: LocalExecutor

**Why We Use It**:
- Industry-standard ETL orchestration tool
- Built-in scheduling and retry logic
- Web UI for monitoring and debugging
- Task dependency management
- XCom for inter-task communication

**How It's Used**:
- **Scheduler**: Automatically triggers DAG runs every 15 minutes
- **Web Server**: Provides UI at http://localhost:8082
- **Tasks**:
  1. `fetch_data` - Downloads data from CKAN API
  2. `validate_data` - Validates raw data integrity
  3. `transform_data` - Transforms and calculates delays
  4. `load_to_db` - Loads data into PostgreSQL

**Key Features**:
- Task retry on failure (1 retry with 5-minute delay)
- Task logging and monitoring
- DAG visualization
- Historical run tracking

---

## Storage Services

### 3. AWS S3 (Amazon Simple Storage Service)
**Type**: Cloud object storage  
**Purpose**: Stores raw and processed flight data with versioning

**Details**:
- **Bucket Name**: `etl-flight-pipeline-bucket`
- **Raw Data Path**: `uploads/flights_data_YYYYMMDD_HHMMSS.json`
- **Processed Data Path**: `processed/flights_data_YYYYMMDD_HHMMSS.csv`
- **Storage Class**: Standard
- **Versioning**: Enabled for data lineage

**Why We Use It**:
- Cost-effective long-term storage
- High durability (99.999999999%)
- Scalable (no size limits)
- Versioned storage for data lineage
- Easy integration with Airflow

**How It's Used**:
- **Raw Storage**: Stores original JSON data from CKAN API
  - Timestamped files for historical tracking
  - Used for data recovery and auditing
- **Processed Storage**: Stores transformed CSV data
  - Cleaned and validated data
  - Ready for database loading
  - Used for reprocessing if needed

**Data Flow**:
1. Airflow uploads raw JSON → S3 `uploads/` folder
2. Airflow transforms data → S3 `processed/` folder
3. Airflow downloads processed CSV → Loads to PostgreSQL

---

### 4. PostgreSQL
**Type**: Relational database management system  
**Purpose**: Stores processed flight data for querying and serving

**Details**:
- **Version**: 16.3
- **Database Name**: `flights_db`
- **Table**: `flights`
- **Port**: 5433 (host), 5432 (container)
- **User**: `daniel`
- **Password**: `daniel`
- **Records**: 9,909+ flight records

**Why We Use It**:
- ACID compliance for data integrity
- Excellent query performance with indexes
- Relational data model fits flight data structure
- Strong ecosystem and tooling
- Easy Docker deployment

**How It's Used**:
- **ETL Pipeline**: Airflow loads transformed data via upsert operations
- **Backend API**: FastAPI queries PostgreSQL for flight data
- **Data Model**: Single `flights` table with all flight information
- **Indexes**: Optimized for common queries (airline, date, direction)

**Schema Highlights**:
- `flight_id` (VARCHAR, Primary Key) - Unique identifier
- `airline_code`, `flight_number`, `direction`
- `scheduled_time`, `actual_time`, `delay_minutes`
- `location_iata`, `terminal`, `status_en`, `status_he`
- `scrape_timestamp`, `raw_s3_path`

**Shared Access**:
- Both Airflow (ETL) and FastAPI (API) use the same database
- Airflow writes data, FastAPI reads data
- No direct communication between services - only through database

---

## Backend Services

### 5. FastAPI
**Type**: Python web framework  
**Purpose**: RESTful API backend for serving flight data

**Details**:
- **Port**: 8000
- **Framework**: FastAPI (Python)
- **Endpoints**: 15+ RESTful endpoints
- **Documentation**: Auto-generated Swagger UI at `/docs`
- **Async Support**: Yes (async/await)

**Why We Use It**:
- High performance (async support)
- Automatic API documentation
- Type hints and validation (Pydantic)
- Modern Python framework
- Easy to develop and maintain

**How It's Used**:
- **API Endpoints**:
  - `/api/v1/flights` - List flights with pagination and filtering
  - `/api/v1/flights/{id}` - Get single flight
  - `/api/v1/flights/search` - Search flights
  - `/api/v1/flights/stats` - Flight statistics
  - `/api/v1/airlines` - List airlines
  - `/api/v1/airlines/stats` - Airline performance KPIs
  - `/api/v1/destinations` - List destinations
  - `/health` - Health check
- **Features**:
  - Pagination (default 50, max 200 per page)
  - Advanced filtering (airline, direction, date, status, delay)
  - Search functionality
  - Analytics and aggregations
  - CORS middleware for frontend access
  - Structured logging (structlog)
  - Error handling

**Key Technologies**:
- **SQLAlchemy**: ORM for database access
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server
- **structlog**: Structured logging

---

## Frontend Services

### 6. React
**Type**: JavaScript frontend framework  
**Purpose**: Interactive web dashboard for visualizing flight data

**Details**:
- **Port**: 3000 (development)
- **Framework**: React 18.3.1
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Build Tool**: Vite

**Why We Use It**:
- Industry-standard frontend framework
- Component-based architecture
- Rich ecosystem and libraries
- TypeScript for type safety
- Fast development with hot reload

**How It's Used**:
- **Dashboard Components**:
  - Flight data table with pagination
  - Airline performance statistics
  - Filter controls (airline, date, direction, status)
  - Search functionality
  - Language toggle (Hebrew/English)
  - Theme toggle (Light/Dark)
- **Features**:
  - Real-time data fetching from FastAPI
  - Interactive filtering and search
  - Responsive design (mobile-friendly)
  - Multi-language support (RTL for Hebrew)
  - Dark/light theme support
  - Error handling and loading states

**Key Technologies**:
- **React Router**: Client-side routing
- **TanStack Query**: Data fetching and caching
- **Radix UI**: Accessible component library
- **Recharts**: Data visualization
- **next-themes**: Theme management
- **date-fns**: Date manipulation

---

## Infrastructure Services

### 7. Docker
**Type**: Containerization platform  
**Purpose**: Package and run services in isolated containers

**Details**:
- **Version**: 20.10+
- **Compose Version**: 1.29+
- **Containers**: 
  - PostgreSQL (backend)
  - PostgreSQL (Airflow metadata)
  - FastAPI backend
  - Airflow webserver
  - Airflow scheduler
  - Airflow init

**Why We Use It**:
- Consistent environments (dev, staging, prod)
- Easy service orchestration
- Isolated dependencies
- Simplified deployment
- Resource management

**How It's Used**:
- **Backend Services**: `backend/docker-compose.yaml`
  - PostgreSQL container for `flights_db`
  - FastAPI backend container
  - Volume management for data persistence
- **Airflow Services**: `airflow/docker-compose.yaml`
  - PostgreSQL container for Airflow metadata
  - Airflow webserver container
  - Airflow scheduler container
  - Volume mounts for DAGs, logs, data

**Benefits**:
- One command to start all services
- Isolated environments prevent conflicts
- Easy cleanup and reset
- Production-ready deployment

---

### 8. Docker Compose
**Type**: Container orchestration tool  
**Purpose**: Define and run multi-container Docker applications

**Details**:
- **Files**: 
  - `backend/docker-compose.yaml`
  - `airflow/docker-compose.yaml`

**Why We Use It**:
- Define all services in YAML
- Automatic service dependencies
- Network management
- Volume management
- Environment variable management

**How It's Used**:
- **Service Definitions**: All containers defined in YAML
- **Dependencies**: Services start in correct order
- **Networking**: Services can communicate via service names
- **Volumes**: Persistent data storage
- **Environment**: Variable injection from `.env` files

---

## Development Tools

### 9. Python
**Type**: Programming language  
**Purpose**: Backend and ETL pipeline development

**Details**:
- **Version**: 3.8+
- **Used In**: 
  - Airflow DAGs and tasks
  - FastAPI backend
  - ETL transformation scripts

**Why We Use It**:
- Excellent data processing libraries (pandas, numpy)
- Strong ecosystem for ETL
- Easy integration with databases
- Great for API development

**Key Libraries**:
- **pandas**: Data manipulation and transformation
- **requests**: HTTP client for API calls
- **boto3**: AWS SDK for S3 access
- **SQLAlchemy**: Database ORM
- **FastAPI**: Web framework

---

### 10. Node.js / npm
**Type**: JavaScript runtime and package manager  
**Purpose**: Frontend development and dependency management

**Details**:
- **Version**: 16+
- **Used In**: React frontend

**Why We Use It**:
- Standard for React development
- Rich package ecosystem
- Fast development server
- Build tooling (Vite)

**Key Packages**:
- React and React DOM
- TypeScript
- Tailwind CSS
- React Router
- TanStack Query

---

### 11. Git
**Type**: Version control system  
**Purpose**: Source code management and collaboration

**Details**:
- **Repository**: Local Git repository
- **Branches**: Feature branches for development

**Why We Use It**:
- Track code changes
- Collaboration
- Version history
- Branch management

---

## Service Communication Flow

```
┌─────────────┐
│  CKAN API   │  (External - Data Source)
└──────┬──────┘
       │ HTTP GET
       ▼
┌─────────────┐
│  Airflow    │  (Orchestration)
│  Scheduler  │
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
   ▼       ▼
┌─────┐ ┌──────────┐
│ S3  │ │PostgreSQL│  (Storage)
└─────┘ └────┬─────┘
             │ SQL Queries
             ▼
      ┌──────────┐
      │ FastAPI  │  (Backend API)
      └────┬─────┘
           │ HTTP REST
           ▼
      ┌──────────┐
      │  React   │  (Frontend)
      └──────────┘
```

---

## Service Dependencies

### Critical Dependencies
1. **Airflow** depends on:
   - PostgreSQL (for metadata)
   - AWS S3 (for data storage)
   - CKAN API (for data source)

2. **FastAPI** depends on:
   - PostgreSQL (for data)

3. **React** depends on:
   - FastAPI (for data)

### Service Startup Order
1. **PostgreSQL** (both instances) - Must start first
2. **Airflow Init** - Initializes Airflow database
3. **Airflow Scheduler** - Starts ETL pipeline
4. **Airflow Webserver** - Provides UI
5. **FastAPI Backend** - Starts API server
6. **React Frontend** - Starts development server

---

## Port Summary

| Service | Port | URL |
|---------|------|-----|
| React Frontend | 3000 | http://localhost:3000 |
| FastAPI Backend | 8000 | http://localhost:8000 |
| FastAPI Docs | 8000 | http://localhost:8000/docs |
| Airflow UI | 8082 | http://localhost:8082 |
| PostgreSQL (Flights) | 5433 | localhost:5433 |
| PostgreSQL (Airflow) | 5432 | localhost:5432 |

---

## Service Responsibilities Summary

| Service | Primary Responsibility | Data Flow |
|---------|----------------------|-----------|
| **CKAN API** | Provide flight data | Source |
| **Airflow** | Orchestrate ETL | Extract → Transform → Load |
| **S3** | Store raw/processed data | Storage (raw & processed) |
| **PostgreSQL** | Store queryable data | Storage (structured) |
| **FastAPI** | Serve data via API | Read & Serve |
| **React** | Visualize data | Display & Interact |
| **Docker** | Containerize services | Infrastructure |

---

## Cost Considerations

### Free/Open Source
- CKAN API (public, free)
- Apache Airflow (open source)
- PostgreSQL (open source)
- FastAPI (open source)
- React (open source)
- Docker (open source)

### Paid Services
- **AWS S3**: Pay-per-use storage
  - Estimated cost: ~$0.023 per GB/month
  - Very low cost for this project size

### Infrastructure Costs
- **Development**: Free (local Docker)
- **Production**: Cloud hosting costs (varies by provider)

---

## Summary

This project uses **7 main services**:

1. **CKAN API** - External data source
2. **Apache Airflow** - ETL orchestration
3. **AWS S3** - Object storage
4. **PostgreSQL** - Relational database
5. **FastAPI** - Backend API
6. **React** - Frontend dashboard
7. **Docker** - Containerization

Each service has a specific purpose and works together to create a complete data pipeline from extraction to visualization. The architecture is designed to be scalable, maintainable, and production-ready.


