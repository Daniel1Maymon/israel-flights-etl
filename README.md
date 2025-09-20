# Israel Flights ETL Project

A modular data pipeline for processing Israeli flight data with Airflow, backend API, and frontend dashboard.

## Project Structure

```
israel-flights-etl/
├── airflow/          # ETL Pipeline (Apache Airflow)
│   ├── dags/         # Airflow DAGs
│   ├── etl/          # ETL scripts
│   ├── utils/        # Utility functions
│   ├── data/         # Data files
│   └── docker-compose.yaml
├── backend/          # API Backend (to be implemented)
└── frontend/         # React Dashboard
```

## Project Flow

```
Israeli API → Airflow ETL → PostgreSQL → Backend API → React Dashboard
     ↓              ↓           ↓
   S3 Storage    S3 Storage   Monitoring
```

## Quick Start

### Airflow ETL Pipeline

1. Navigate to the airflow directory:
   ```bash
   cd airflow
   ```

2. Start the services:
   ```bash
   docker-compose up -d
   ```

3. Access Airflow UI:
   - URL: http://localhost:8080
   - Username: `admin`
   - Password: `admin`

### Frontend Dashboard

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

## Database Access

- **Host**: localhost
- **Port**: 5433
- **Database**: flights_db
- **Username**: daniel
- **Password**: daniel

## Data

The pipeline processes Israeli flight data and stores it in PostgreSQL. Currently contains ~9,909 flight records.

## Environment Variables

Create a `.env` file in the root directory with:
- AWS credentials
- PostgreSQL credentials
- S3 bucket configuration

See `.env.example` for reference.
