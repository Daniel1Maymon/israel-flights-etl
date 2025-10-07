# Israel Flights ETL System

A comprehensive end-to-end data pipeline for processing and visualizing Israeli flight data with advanced analytics, real-time filtering, and production-ready features.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.8+ (for local development)
- Node.js 16+ (for frontend development)

### Running the Complete System

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd israel-flights-etl
   ```

2. **Start all services with Docker Compose:**
   ```bash
   # Start ETL pipeline (Airflow + PostgreSQL)
   cd airflow && docker-compose up -d
   
   # Start Backend API
   cd ../backend && docker-compose up -d
   
   # Start Frontend (development)
   cd ../frontend && npm install && npm run dev
   ```

3. **Access the applications:**
   - **Frontend Dashboard**: http://localhost:3000
   - **Backend API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs
   - **Airflow UI**: http://localhost:8080

## 📁 Project Structure

```
israel-flights-etl/
├── docs/                       # 📚 All documentation
├── airflow/                    # 🔄 ETL Pipeline (Airflow)
├── backend/                    # 🚀 FastAPI Backend
├── frontend/                   # 🎨 React Frontend
├── data/                       # 📊 Data storage
└── utils/                      # 🛠️ Shared utilities
```

## 🏗️ Architecture Overview

**Data Flow**: CKAN API → S3 (raw) → Airflow (ETL) → PostgreSQL (clean) → FastAPI (serve) → React (visualize)

### Key Components

- **ETL Pipeline**: Automated data extraction, transformation, and loading every 15 minutes
- **Backend API**: 15+ RESTful endpoints with advanced filtering and analytics
- **Frontend Dashboard**: Interactive React dashboard with real-time data switching
- **Analytics Engine**: Sophisticated airline performance KPIs and data quality assessment

## 📚 Documentation

All project documentation is organized in the [`docs/`](docs/) folder:

- **[📋 Documentation Index](docs/INDEX.md)** - Complete documentation overview
- **[🏗️ System Architecture](docs/BACKEND_SYSTEM_DESIGN.md)** - Detailed architecture and design
- **[📋 Project Tasks](docs/PROJECT_TASKS.md)** - Current development priorities
- **[🎯 Backend API](docs/BACKEND_SPECIFICATION.md)** - API specification and endpoints
- **[🎨 Frontend Guide](docs/FRONTEND_README.md)** - Frontend documentation

## ✨ Features

### ETL Pipeline
- **Automated Data Extraction** from Israel's official flight data API
- **Data Validation** and quality checks at each stage
- **S3 Storage** for raw and processed data versioning
- **PostgreSQL Integration** with upsert logic for data consistency

### Backend API
- **15+ RESTful Endpoints** for comprehensive data access
- **Advanced Filtering** by airline, destination, date, status, and more
- **Real-time Analytics** with airline performance KPIs
- **Production-Ready** with logging, error handling, and health checks

### Frontend Dashboard
- **Interactive Data Visualization** with real-time updates
- **Multi-language Support** (Hebrew/English)
- **Theme Switching** (Light/Dark mode)
- **Advanced Filtering** and search capabilities
- **Responsive Design** for all device sizes

## 🛠️ Development

### Local Development Setup

1. **Backend Development:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python -m app.main
   ```

2. **Frontend Development:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **ETL Pipeline Development:**
   ```bash
   cd airflow
   # Follow Airflow setup instructions in docs/
   ```

### Testing

- **Backend Tests**: `cd backend && python test_basic.py`
- **Frontend Tests**: `cd frontend && npm test`
- **API Testing**: Visit http://localhost:8000/docs for interactive testing

## 🚀 Deployment

### Production Deployment

The system is designed for cloud deployment with:
- **Container Orchestration** (Docker Swarm/Kubernetes)
- **Database Scaling** (PostgreSQL with connection pooling)
- **Load Balancing** (Nginx/HAProxy)
- **Monitoring** (Prometheus/Grafana)

See [docs/BACKEND_SYSTEM_DESIGN.md](docs/BACKEND_SYSTEM_DESIGN.md) for detailed deployment architecture.

## 📊 Data Sources

- **Primary Source**: [Israel Open Data Portal](https://data.gov.il) - Flight data API
- **Data Format**: JSON with 1000+ records per batch
- **Update Frequency**: Every 15 minutes via Airflow DAG
- **Data Quality**: Automated validation and completeness checks

## 🤝 Contributing

1. Review [docs/RULES.md](docs/RULES.md) for development guidelines
2. Check [docs/PROJECT_TASKS.md](docs/PROJECT_TASKS.md) for current priorities
3. Follow the architecture patterns in [docs/BACKEND_SYSTEM_DESIGN.md](docs/BACKEND_SYSTEM_DESIGN.md)

## 📄 License

This project is licensed under the terms specified in [docs/LICENSE](docs/LICENSE).

## 🆘 Support

For questions and issues:
1. Check the [documentation](docs/INDEX.md)
2. Review [troubleshooting guides](docs/BACKEND_SYSTEM_DESIGN.md#troubleshooting)
3. Check application logs and health endpoints

---

**Built with ❤️ for the Israeli aviation community**
