# Data Flow Diagram - Israel Flights ETL System

## Overview
This document describes how data moves through the Israel Flights ETL system from the CKAN API source to the React Dashboard visualization.

## Data Flow Architecture

```
DATA FLOW DIAGRAM - Israel Flights ETL System
===============================================

SOURCE LAYER
    CKAN API (data.gov.il)
    ↓ (HTTP requests with pagination)
    Resource ID: e83f763b-b7d7-479e-b172-ae981ddc6de5

EXTRACT STAGE
    Airflow Scheduler (every 15 minutes)
    ↓ (fetch_data task)
    Extract raw flight data via pagination (1000 records/batch)
    ↓ (validate_data task)
    Validate file integrity and schema
    ↓ (upload to S3)
    S3 Raw Storage: s3://bucket/raw/flights_data_YYYYMMDD_HHMMSS.json

TRANSFORM STAGE
    Airflow Transform Task
    ↓ (download from S3)
    Download JSON from S3 to temporary file
    ↓ (transform_flight_data)
    Add delay_minutes calculation (actual_time - scheduled_time)
    Apply data cleaning and formatting
    ↓ (convert to CSV)
    Convert transformed data to CSV format
    ↓ (upload processed data)
    S3 Processed Storage: s3://bucket/processed/flights_data_YYYYMMDD_HHMMSS.csv

LOAD STAGE
    Airflow Load Task
    ↓ (download processed CSV)
    Download processed CSV from S3
    ↓ (compute_flight_uuid)
    Generate unique flight_id using natural keys
    ↓ (upsert to database)
    PostgreSQL Database (port 5432)
    flights table with 9,909+ records

SERVE STAGE
    FastAPI Backend (port 8000)
    ↓ (REST API endpoints)
    /api/v1/flights/ - Paginated flight data with filtering
    /api/v1/airlines/stats - Airline performance KPIs
    /api/v1/airlines/destinations - Destination data
    ↓ (HTTP responses)
    JSON data with pagination and filtering

VISUALIZE STAGE
    React Frontend (port 3000)
    ↓ (API calls)
    Fetch data from FastAPI endpoints
    ↓ (component rendering)
    Interactive Dashboard with filters
    Airline performance tables
    Real-time data switching
    Multi-language support (Hebrew/English)
    Theme support (light/dark)
```

## Key Data Transformations

### Extract Phase
- **Source**: CKAN API (data.gov.il)
- **Method**: HTTP requests with pagination (1000 records per batch)
- **Output**: Raw JSON data stored in S3
- **Frequency**: Every 15 minutes
- **Validation**: Schema validation and file integrity checks

### Transform Phase
- **Input**: Raw JSON from S3
- **Processing**: 
  - Calculate delay_minutes (actual_time - scheduled_time)
  - Data cleaning and formatting
  - Convert to CSV format
- **Output**: Processed CSV data stored in S3
- **Quality Checks**: Data completeness and validation

### Load Phase
- **Input**: Processed CSV from S3
- **Processing**:
  - Generate unique flight_id using natural keys
  - Upsert logic to handle duplicates
- **Output**: Clean data in PostgreSQL database
- **Storage**: flights table with indexed columns for performance

### Serve Phase
- **Input**: PostgreSQL database queries
- **Processing**: 
  - Advanced filtering and pagination
  - Airline performance KPI calculations
  - Data aggregation and statistics
- **Output**: RESTful API responses in JSON format

### Visualize Phase
- **Input**: API responses from FastAPI
- **Processing**:
  - Real-time data switching (mock vs database)
  - Interactive filtering and sorting
  - Multi-language and theme support
- **Output**: Interactive React dashboard

## Data Quality Flow

```
Data Quality Checks
===================

EXTRACT VALIDATION
    ✓ Schema validation (required fields present)
    ✓ Record count validation (minimum threshold)
    ✓ API response structure validation
    ✓ Data type validation

TRANSFORM VALIDATION
    ✓ Data completeness checks
    ✓ Delay calculation validation
    ✓ CSV format validation
    ✓ File integrity verification

LOAD VALIDATION
    ✓ Database connection validation
    ✓ Upsert operation validation
    ✓ Row count verification
    ✓ Data consistency checks

SERVE VALIDATION
    ✓ API endpoint health checks
    ✓ Database query validation
    ✓ Response format validation
    ✓ Error handling validation
```

## Error Handling Flow

```
Error Handling Strategy
=======================

EXTRACT ERRORS
    API Request Failed → Retry with exponential backoff
    Invalid Response → Log error and skip batch
    Network Timeout → Retry with increased timeout

TRANSFORM ERRORS
    Data Validation Failed → Log error and continue
    File Processing Error → Retry with cleanup
    S3 Upload Failed → Retry with new credentials

LOAD ERRORS
    Database Connection Failed → Retry with connection pool
    Upsert Operation Failed → Log error and continue
    Data Integrity Violation → Skip problematic records

SERVE ERRORS
    API Endpoint Error → Return appropriate HTTP status
    Database Query Error → Log error and return empty result
    Validation Error → Return 400 Bad Request

VISUALIZE ERRORS
    API Call Failed → Show error message to user
    Data Loading Error → Display loading state
    Network Error → Retry with user notification
```

## Performance Considerations

### Extract Performance
- **Pagination**: 1000 records per batch to optimize memory usage
- **Parallel Processing**: Multiple API calls can be made concurrently
- **Caching**: S3 provides fast access to raw data

### Transform Performance
- **Streaming**: Process data in chunks to avoid memory issues
- **Temporary Files**: Use local storage for intermediate processing
- **Cleanup**: Automatic cleanup of temporary files

### Load Performance
- **Upsert Logic**: Efficient handling of duplicate records
- **Batch Operations**: Bulk insert/update operations
- **Indexing**: Database indexes for fast query performance

### Serve Performance
- **Connection Pooling**: Reuse database connections
- **Query Optimization**: Efficient SQL queries with proper indexing
- **Caching**: Response caching for frequently accessed data

### Visualize Performance
- **Lazy Loading**: Load data only when needed
- **Pagination**: Limit data transfer with pagination
- **Caching**: Client-side caching of API responses
