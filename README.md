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
   # Start all backend services (ETL + Database + API)
   docker compose up -d --build

   # Or for production deployment
   docker compose -f docker-compose-prod.yml --env-file .env.prod up -d --build
   ```

3. **Access the applications:**
   - **Frontend Dashboard**: Deployed on Vercel (see deployment section)
   - **Backend API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs

## 📁 Project Structure

```
israel-flights-etl/
├── docs/                       # 📚 All documentation
├── etl/                        # 🔄 ETL Pipeline (Lightweight Python Scheduler)
├── backend/                    # 🚀 FastAPI Backend
├── frontend/                   # 🎨 React Frontend (deployed on Vercel)
├── data/                       # 📊 Data storage
└── DEPLOYMENT.md               # 📖 Deployment guide
```

## 🏗️ Architecture Overview

**Data Flow**: CKAN API → ETL Runner (scheduled) → PostgreSQL (clean) → FastAPI (serve) → React (visualize)

### Key Components

- **ETL Pipeline**: Automated data extraction, transformation, and loading every 15 minutes using a lightweight Python scheduler
- **Backend API**: 15+ RESTful endpoints with advanced filtering and analytics
- **Frontend Dashboard**: Interactive React dashboard deployed on Vercel
- **Analytics Engine**: Sophisticated airline performance KPIs and data quality assessment

## 📚 Documentation

All project documentation is organized in the [`docs/`](docs/) folder:

- **[Project Guide](docs/guides/PROJECT_GUIDE.md)** - Complete end-to-end guide (setup, run, troubleshooting)
- **[Services Summary](docs/services/SERVICES_SUMMARY.md)** - What each service does and how it's used
- **[System Architecture](docs/architecture/BACKEND_SYSTEM_DESIGN.md)** - Detailed architecture and design
- **[Backend API Spec](docs/api/BACKEND_SPECIFICATION.md)** - API endpoints and behavior
- **[Field Mapping](docs/reference/FIELD_MAPPING_TABLE.md)** - Source→target field mapping
- **[EC2 Deployment](DEPLOYMENT.md)** - Deploy on a VM with Docker Compose

## ✨ Features

### ETL Pipeline
- **Automated Data Extraction** from Israel's official flight data API
- **Lightweight Scheduler** using APScheduler (no Airflow overhead)
- **Data Validation** and quality checks at each stage
- **PostgreSQL Integration** with upsert logic for data consistency
- **Configurable Schedule** (default: every 15 minutes)

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
- **Deployed on Vercel** for optimal CDN performance

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
   cd etl
   # Install dependencies
   pip install -r requirements.txt
   # Run ETL manually
   python -m etl.main
   ```

### Testing

- **Backend Tests**: `cd backend && python test_basic.py`
- **Frontend Tests**: `cd frontend && npm test`
- **API Testing**: Visit http://localhost:8000/docs for interactive testing

## 🚀 Deployment

### Production Deployment

The system is designed for cloud deployment with:
- **Backend & Database**: Docker Compose on EC2
- **Frontend**: Vercel (automatic deployments from Git)
- **ETL Runner**: Docker container with APScheduler on EC2
- **Database**: PostgreSQL with persistent volumes

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

### Deployment Architecture

- **Frontend**: Deployed on Vercel
  - Automatic builds from Git pushes
  - Global CDN distribution
  - Environment variable configuration via Vercel dashboard

- **Backend**: Deployed on EC2 with Docker Compose
  - PostgreSQL database
  - FastAPI backend
  - Lightweight ETL runner with APScheduler

## 📊 Data Sources

- **Primary Source**: [Israel Open Data Portal](https://data.gov.il) - Flight data API
- **Data Format**: JSON with 1000+ records per batch
- **Update Frequency**: Every 15 minutes via scheduled ETL runner
- **Data Quality**: Automated validation and completeness checks

## 🤝 Contributing

1. Start with [docs/guides/PROJECT_GUIDE.md](docs/guides/PROJECT_GUIDE.md)
2. Follow the architecture patterns in [docs/architecture/BACKEND_SYSTEM_DESIGN.md](docs/architecture/BACKEND_SYSTEM_DESIGN.md)

## 📄 License

This project is licensed under the terms specified in [docs/LICENSE](docs/LICENSE).

## 🆘 Support

For questions and issues:
1. Start with [docs/guides/PROJECT_GUIDE.md](docs/guides/PROJECT_GUIDE.md)
2. Review [troubleshooting guides](docs/architecture/BACKEND_SYSTEM_DESIGN.md#troubleshooting)
3. Check application logs and health endpoints

---

**Built with ❤️ for the Israeli aviation community**
