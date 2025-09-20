# Israel Flights API Backend

A production-ready FastAPI backend for serving Israeli flight data from the ETL pipeline.

## Features

- **RESTful API** with comprehensive flight data endpoints
- **Advanced Filtering** by direction, airline, status, terminal, date range, and delay
- **Search Functionality** across multiple fields
- **Pagination** with configurable page sizes
- **Statistics** with grouping by airline, destination, hour, or day
- **Health Checks** for monitoring and load balancers
- **Production Ready** with security, monitoring, and error handling
- **Docker Support** for easy deployment
- **Comprehensive Testing** with automated test suite

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL running on localhost:5433
- Database `flights_db` with `flights` table populated

### Development Setup

1. **Clone and navigate to backend:**
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
   curl "http://localhost:8000/api/v1/flights?page=1&size=5"
   ```

### Docker Setup

1. **Using Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Using Docker:**
   ```bash
   docker build -t israel-flights-api .
   docker run -p 8000:8000 israel-flights-api
   ```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Core Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check (includes database)
- `GET /metrics` - Basic metrics

### Flight Endpoints

- `GET /api/v1/flights` - List flights with pagination and filtering
- `GET /api/v1/flights/{flight_id}` - Get specific flight
- `GET /api/v1/flights/search` - Search flights
- `GET /api/v1/flights/stats` - Flight statistics
- `GET /api/v1/flights/airlines` - List airlines
- `GET /api/v1/flights/destinations` - List destinations

### Example Requests

```bash
# List flights with pagination
curl "http://localhost:8000/api/v1/flights?page=1&size=10"

# Filter by airline and direction
curl "http://localhost:8000/api/v1/flights?airline_code=LY&direction=D"

# Search flights
curl "http://localhost:8000/api/v1/flights/search?q=Tel%20Aviv"

# Get statistics
curl "http://localhost:8000/api/v1/flights/stats?group_by=airline"

# List airlines
curl "http://localhost:8000/api/v1/flights/airlines?search=El%20Al"
```

## Testing

### Automated Tests

Run the comprehensive test suite:

```bash
python test_basic.py
```

### Manual Testing

Test individual endpoints:

```bash
# Health check
curl http://localhost:8000/health

# List flights
curl "http://localhost:8000/api/v1/flights?page=1&size=5"

# Search flights
curl "http://localhost:8000/api/v1/flights/search?q=LY"

# Get statistics
curl http://localhost:8000/api/v1/flights/stats
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Database
DATABASE_URL=postgresql://daniel:daniel@localhost:5433/flights_db
DB_HOST=localhost
DB_PORT=5433
DB_NAME=flights_db
DB_USER=daniel
DB_PASSWORD=daniel

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Pagination
DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=200
```

See `.env.example` for all available options.

## Production Deployment

### Docker Production

```bash
# Build production image
docker build -t israel-flights-api:latest .

# Run with production settings
docker run -d \
  --name israel-flights-api \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:port/db" \
  -e CORS_ORIGINS="https://yourdomain.com" \
  israel-flights-api:latest
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: israel-flights-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: israel-flights-api
  template:
    metadata:
      labels:
        app: israel-flights-api
    spec:
      containers:
      - name: api
        image: israel-flights-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
```

## Monitoring

### Health Checks

- **Liveness**: `GET /health` - Application is running
- **Readiness**: `GET /ready` - Application can serve traffic
- **Metrics**: `GET /metrics` - Basic performance metrics

### Logging

Structured JSON logging with:
- Request/response logging
- Error tracking
- Performance metrics
- Database query logging

### Metrics

Prometheus-compatible metrics:
- Request count and duration
- Error rates
- Database connection health
- Custom business metrics

## Security

### Production Security Features

- **Rate Limiting**: 100 requests/minute per IP
- **Input Validation**: All inputs sanitized and validated
- **SQL Injection Prevention**: Parameterized queries only
- **CORS Configuration**: Restrictive origin allowlist
- **Security Headers**: HSTS, X-Frame-Options, etc.
- **Secret Management**: Environment-based configuration

### Authentication (Optional)

For production, add API key authentication:

```python
# Add to dependencies
def verify_api_key(api_key: str = Header(...)):
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
```

## Performance

### Optimization Features

- **Connection Pooling**: Optimized database connections
- **Query Optimization**: Efficient SQL queries with proper indexing
- **Pagination**: Prevents large result sets
- **Caching**: Redis support for frequently accessed data
- **Async Support**: Non-blocking request handling

### Expected Performance

- **Response Time**: < 200ms for 50 flights
- **Throughput**: 1000+ requests/minute
- **Concurrent Users**: 100+ simultaneous connections

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify connection string
   - Check network connectivity

2. **CORS Errors**
   - Verify CORS_ORIGINS setting
   - Check frontend URL matches allowed origins

3. **High Memory Usage**
   - Reduce MAX_CONNECTIONS
   - Enable connection pooling
   - Check for memory leaks

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m app.main
```

## Development

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── flight.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── __init__.py
│   │   └── flight.py
│   ├── api/                 # API routes
│   │   ├── __init__.py
│   │   ├── deps.py          # Dependencies
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── flights.py
│   └── utils/               # Utility functions
│       ├── __init__.py
│       └── filters.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml
├── test_basic.py
└── README.md
```

### Adding New Endpoints

1. Add route to `app/api/v1/flights.py`
2. Update schemas in `app/schemas/flight.py`
3. Add tests to `test_basic.py`
4. Update documentation

## License

This project is part of the Israel Flights ETL system.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Check application logs
4. Run the test suite to verify functionality