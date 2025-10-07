# System Architecture Diagram - Israel Flights ETL System

## Overview
This document describes the system architecture of the Israel Flights ETL system, showing the different layers and their components, along with the main connections between them.

## System Architecture

```
SYSTEM ARCHITECTURE DIAGRAM - Israel Flights ETL System
========================================================

SOURCE LAYER
    CKAN API (data.gov.il)
    - Public Israeli flight data API
    - Resource ID: e83f763b-b7d7-479e-b172-ae981ddc6de5
    - Provides real-time flight information
    - RESTful API with pagination support
    - Data format: JSON

ORCHESTRATION LAYER
    Apache Airflow
    - Scheduler: Runs every 15 minutes (*/15 * * * *)
    - DAG: flight_data_pipeline
    - Tasks: fetch_data → validate_data → transform_data → load_to_db
    - Retry policy: 1 retry with 5-minute delay
    - XCom for task communication
    - Web UI: http://localhost:8080
    - Monitoring and logging capabilities

STORAGE LAYER
    Amazon S3
    - Raw data: s3://bucket/raw/flights_data_YYYYMMDD_HHMMSS.json
    - Processed data: s3://bucket/processed/flights_data_YYYYMMDD_HHMMSS.csv
    - Versioned storage for data lineage
    - Cost-effective long-term storage
    - High availability and durability
    
    PostgreSQL Database (port 5432)
    - Database: postgres_flights
    - Table: flights (9,909+ records)
    - Indexed for performance
    - Connection pooling enabled
    - ACID compliance
    - Shared between ETL and API layers

SERVING LAYER
    FastAPI Backend (port 8000)
    - 15+ RESTful endpoints
    - Advanced filtering and pagination
    - Airline analytics and KPI calculations
    - Structured logging with structlog
    - CORS middleware for frontend access
    - Health checks and error handling
    - Auto-generated API documentation
    - Async request processing
    
    Key API Endpoints:
    - /api/v1/flights/ - Flight data with filtering
    - /api/v1/airlines/stats - Airline performance metrics
    - /api/v1/airlines/destinations - Destination data
    - /api/v1/airlines/{airline_code}/destinations - Airline-specific destinations
    - /api/v1/flights/airlines - Unique airlines list
    - /api/v1/flights/destinations - Unique destinations list

PRESENTATION LAYER
    React Frontend (port 3000)
    - TypeScript with Tailwind CSS
    - Interactive dashboard components
    - Real-time data switching (mock vs database)
    - Multi-language support (Hebrew/English)
    - Theme support (light/dark)
    - Responsive design with mobile support
    - Modern UI with accessibility features
    
    Key Components:
    - DashboardFilters - Filter controls
    - AirlineTable - Performance tables
    - PaginatedFlightsTable - Flight data table
    - ThemeToggle/LanguageToggle - UI controls
    - DatabaseToggle - Data source switching
```

## Main Connections Between Layers

```
LAYER CONNECTIONS
=================

DATA INGESTION CONNECTIONS
    CKAN API → Airflow Scheduler
    - HTTP requests with pagination
    - Resource ID: e83f763b-b7d7-479e-b172-ae981ddc6de5
    - Frequency: Every 15 minutes
    - Error handling and retry logic

STORAGE CONNECTIONS
    Airflow → S3 (Raw Data)
    - Upload raw JSON data
    - Path: s3://bucket/raw/flights_data_YYYYMMDD_HHMMSS.json
    - Versioned storage for data lineage
    
    Airflow → S3 (Processed Data)
    - Upload processed CSV data
    - Path: s3://bucket/processed/flights_data_YYYYMMDD_HHMMSS.csv
    - Cleaned and transformed data
    
    Airflow → PostgreSQL
    - Upsert operations for data loading
    - Database: postgres_flights
    - Table: flights
    - Handles duplicates with conflict resolution

SERVING CONNECTIONS
    FastAPI → PostgreSQL
    - Database queries for data retrieval
    - Connection pooling for performance
    - SQLAlchemy ORM for data access
    - Advanced filtering and pagination
    
    React → FastAPI
    - HTTP API calls for data
    - RESTful endpoints
    - JSON data exchange
    - CORS enabled for cross-origin requests

MONITORING CONNECTIONS
    Airflow → Logging System
    - Task execution logs
    - Error tracking and alerting
    - Performance metrics
    
    FastAPI → Logging System
    - Request/response logging
    - Error tracking
    - Performance monitoring
    
    React → Browser Console
    - Client-side error logging
    - Debug information
    - User interaction tracking
```

## Component Details

### Source Layer Components

```
CKAN API (data.gov.il)
    Purpose: Public data source for Israeli flight information
    Technology: RESTful API
    Data Format: JSON
    Authentication: None (public API)
    Rate Limiting: Built-in pagination support
    Reliability: High availability government service
    Data Freshness: Real-time updates
```

### Orchestration Layer Components

```
Apache Airflow
    Purpose: ETL pipeline orchestration and scheduling
    Technology: Python-based workflow engine
    Scheduling: Cron-based (every 15 minutes)
    Monitoring: Web UI with task status tracking
    Error Handling: Retry logic with exponential backoff
    Scalability: Horizontal scaling support
    Extensibility: Plugin architecture for custom operators
```

### Storage Layer Components

```
Amazon S3
    Purpose: Raw and processed data storage
    Technology: Object storage service
    Features: Versioning, lifecycle policies, encryption
    Performance: High throughput and low latency
    Cost: Pay-per-use pricing model
    Durability: 99.999999999% (11 9's)
    Availability: 99.99% uptime SLA

PostgreSQL Database
    Purpose: Structured data storage and querying
    Technology: Relational database management system
    Features: ACID compliance, full-text search, JSON support
    Performance: Optimized with indexes and connection pooling
    Scalability: Read replicas and partitioning support
    Backup: Automated backups with point-in-time recovery
```

### Serving Layer Components

```
FastAPI Backend
    Purpose: RESTful API for data access and analytics
    Technology: Python web framework with async support
    Features: Auto-generated documentation, type hints, validation
    Performance: High-performance async request handling
    Security: CORS, input validation, error handling
    Monitoring: Structured logging and health checks
    Documentation: Interactive API docs at /docs endpoint
```

### Presentation Layer Components

```
React Frontend
    Purpose: Interactive user interface for data visualization
    Technology: React with TypeScript and Tailwind CSS
    Features: Responsive design, multi-language, theme support
    Performance: Client-side routing and lazy loading
    Accessibility: WCAG compliance and keyboard navigation
    State Management: React hooks and context API
    Build Tool: Vite for fast development and building
```

## Data Flow Between Components

```
COMPLETE DATA FLOW
==================

1. DATA EXTRACTION
   CKAN API → Airflow Scheduler → S3 Raw Storage
   - Every 15 minutes
   - Paginated data retrieval
   - JSON format storage

2. DATA TRANSFORMATION
   S3 Raw Storage → Airflow Transform → S3 Processed Storage
   - Data cleaning and validation
   - Delay calculations
   - CSV format conversion

3. DATA LOADING
   S3 Processed Storage → Airflow Load → PostgreSQL
   - Upsert operations
   - Duplicate handling
   - Data integrity checks

4. DATA SERVING
   PostgreSQL → FastAPI → React Frontend
   - RESTful API queries
   - Real-time data access
   - Interactive visualization

5. USER INTERACTION
   React Frontend → FastAPI → PostgreSQL
   - Filter and search requests
   - Pagination and sorting
   - Analytics and reporting
```

## Security Architecture

```
SECURITY LAYERS
================

NETWORK SECURITY
    - HTTPS encryption for all API communications
    - CORS configuration for cross-origin requests
    - Firewall rules for port access control

DATA SECURITY
    - S3 server-side encryption for data at rest
    - PostgreSQL connection encryption
    - Secure credential management

APPLICATION SECURITY
    - Input validation and sanitization
    - SQL injection prevention
    - Error handling without information disclosure
    - Rate limiting and request throttling

MONITORING SECURITY
    - Audit logging for all operations
    - Security event monitoring
    - Anomaly detection and alerting
    - Regular security assessments
```

## Scalability Considerations

```
SCALABILITY STRATEGY
====================

HORIZONTAL SCALING
    - Airflow: Multiple worker nodes
    - FastAPI: Load balancer with multiple instances
    - PostgreSQL: Read replicas for query distribution
    - S3: Automatic scaling with no configuration needed

VERTICAL SCALING
    - Database: Increased memory and CPU resources
    - Application servers: More powerful hardware
    - Storage: Higher performance storage tiers

CACHING STRATEGY
    - Database query result caching
    - API response caching
    - CDN for static frontend assets
    - Redis for session and data caching

PERFORMANCE OPTIMIZATION
    - Database indexing for fast queries
    - Connection pooling for database access
    - Async processing for I/O operations
    - Lazy loading for frontend components
```
