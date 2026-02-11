# Deployment Guide

This guide will help you deploy the Israel Flights ETL project on an EC2 instance using Docker Compose.

## Architecture Overview

- **Frontend**: Deployed on **Vercel** (separate from EC2)
- **Backend API**: Deployed on EC2 via Docker Compose
- **ETL Runner**: Lightweight Python scheduler deployed on EC2 via Docker Compose
- **Database**: PostgreSQL deployed on EC2 via Docker Compose

## Prerequisites

1. **EC2 Instance** (Ubuntu 22.04 LTS recommended)
   - Optimal (recommended for this workload): 1-2 vCPU, 2GB RAM, 15GB storage
   - Minimum (tight but workable): 1 vCPU, 1.5GB RAM, 10GB storage
   - Safe (over-provisioned but fine): 2 vCPU, 4GB RAM, 20GB storage
   - Suggested instance types: `t4g.micro`, `t4g.small`, or `t3.small`

2. **Security Group Configuration**
   - Open port 8000 (Backend API)
   - Open port 22 (SSH) for access

3. **AWS Credentials** (if using S3 for backups)
   - AWS Access Key ID
   - AWS Secret Access Key
   - IAM permissions for S3 access

4. **Vercel Account** (for frontend deployment)
   - The frontend is deployed separately on Vercel
   - See "Frontend Deployment" section below

## EC2 Sizing Analysis

### Executive Summary

Conclusion: The stated EC2 requirements are significantly overestimated for this workload.

- Stated Minimum (2 vCPU, 4GB RAM): 3-4x larger than necessary
- Stated Recommended (4 vCPU, 8GB RAM): 6-8x larger than necessary
- Actual Suitable Spec: 1 vCPU, 1-2GB RAM, 10GB storage

---

### Detailed Analysis

#### 1. Architecture & Runtime Components

Based on `docker-compose-prod.yml`, the EC2 instance runs only 3 containers:

1. PostgreSQL 16.3 (`postgres_flights`). Single database: `flights_db`. ~10,000 flight records. Simple schema (21 columns, no complex indexes).
2. ETL Runner (`etl` service). Lightweight Python scheduler (APScheduler). Runs every 15 minutes (configurable). Single-threaded, no parallelism. Dependencies: `requests`, `pandas`, `psycopg2-binary`, `apscheduler`. Code size: 136KB.
3. FastAPI Backend (`backend` service). Gunicorn with 4 Uvicorn workers. 15+ REST API endpoints (read-only queries). No heavy computation. Code size: 415MB (including dependencies).

Important: Frontend is deployed on Vercel, not EC2. It consumes zero EC2 resources.

---

#### 2. Resource Consumption Analysis

CPU Usage

- ETL Runner (runs every 15 minutes): Fetches 1,000-2,000 records via HTTP API (I/O-bound, not CPU-bound). Pandas DataFrame transformations on ~1-2K rows (trivial workload). Database upserts using `executemany()` (I/O-bound). Estimated CPU per run: <5% of 1 vCPU for ~10-30 seconds. Average CPU: essentially idle (runs 4x/hour for <30s each).
- FastAPI Backend: 4 Uvicorn workers handle HTTP requests. Queries PostgreSQL and returns JSON (I/O-bound). No CPU-intensive operations (no ML, no video processing, no heavy computation). Estimated CPU: <10-20% of 1 vCPU under moderate load.
- PostgreSQL: Stores ~10,000 simple records. Simple SELECT queries with filters. Occasional upsert operations (every 15 min). Estimated CPU: <10% of 1 vCPU.

Total CPU Need: 0.5-1 vCPU is sufficient for this workload.

---

Memory Usage

- PostgreSQL: Data ~50-100MB for 10,000 flight records. Buffer cache ~50-100MB. Connection overhead ~50MB. Estimated total: ~200-300MB.
- ETL Runner: Python runtime ~50MB. Pandas + DataFrame (1-2K rows) ~50-100MB. HTTP client buffers ~20MB. Estimated total: ~100-200MB.
- FastAPI Backend: 4 Uvicorn workers x ~50MB each ~200MB. SQLAlchemy connection pool ~50MB. Request/response buffers ~50MB. Estimated total: ~300-400MB.
- System Overhead: ~200-300MB.

Total Memory Need: 800MB - 1.2GB realistically, 1.5-2GB with comfortable headroom.

---

Storage Usage

- Code & Dependencies: ~500MB (backend + ETL + system packages)
- PostgreSQL Data: ~100MB (10,000 records + indexes)
- Docker Images: ~2-3GB (PostgreSQL, Python base images)
- Logs: ~500MB-1GB (generous estimate)
- OS & System: ~2-3GB (Ubuntu base)

Total Storage Need: 5-8GB, comfortably fits in 10GB, well below stated 20GB.

---

#### 3. Workload Characteristics

Concurrency

- Backend: 4 workers handle concurrent HTTP requests
- ETL: Single-threaded (no multiprocessing/threading found in code)
- No parallel data processing

I/O Pattern

- Network: Outbound HTTP to CKAN API every 15 min, inbound API requests
- Disk: Minimal (PostgreSQL writes, application logs)
- Database: Light read/write pattern

Traffic Assumptions

- Assuming low-moderate traffic (typical dashboard: <100 req/min)
- API endpoints are simple queries (no aggregation complexity)
- No user uploads or heavy POST operations

---

#### 4. Comparison: Stated vs. Actual Requirements

```
Resource | Stated Min | Stated Rec | Actual Need | Overestimate Factor
vCPU     | 2          | 4          | 0.5-1       | 2-8x
RAM      | 4GB        | 8GB        | 1-2GB       | 2-8x
Storage  | 20GB       | 20GB       | 10GB        | 2x
```

---

#### 5. What Would Break with Smaller Resources?

Running on 1 vCPU, 1GB RAM, 10GB storage:

Risks

- Memory pressure if traffic spikes unexpectedly
- ETL may slow down during pandas transformations (but still completes)
- No headroom for temporary memory spikes
- OOM kills if memory leak exists

Mitigation

- Reduce backend workers from 4 to 2
- Add swap space (1-2GB)
- Monitor memory usage

Running on stated "Minimum" (2 vCPU, 4GB RAM):

Result: Massive resource waste

- CPU: 75-90% idle at all times
- RAM: 2-3GB unused
- Cost: Paying 2-4x more than necessary

---

#### 6. Assumptions Made

1. Traffic: Assuming <100 requests/minute to backend API (moderate dashboard usage)
2. Data Growth: Assuming flight records grow linearly, not exponentially
3. No Peak Traffic: Not accounting for viral spikes or DDoS
4. Efficient Code: Assuming no memory leaks in application code
5. Single Region: No multi-region replication or high availability requirements
6. Development/Staging: These specs are for production, not dev/staging

---

#### 7. Revised Recommendations

For Production (Single-Instance, Moderate Traffic)

Scenario: Minimum (Tight). vCPU: 1. RAM: 1.5GB. Storage: 10GB. Notes: Reduce workers to 2, add swap.

Scenario: Recommended (Comfortable). vCPU: 1-2. RAM: 2GB. Storage: 15GB. Notes: Allows for growth and headroom.

Scenario: Safe (Future-Proof). vCPU: 2. RAM: 4GB. Storage: 20GB. Notes: Stated "minimum" is actually overkill but safe.

AWS Instance Type Recommendations

- Cost-Optimized: t4g.micro or t4g.small (1-2 vCPU, 1-2GB) - ~$6-12/month
- Comfortable: t4g.small or t3.small (2 vCPU, 2GB) - ~$12-15/month
- Current "Minimum": t3.medium (2 vCPU, 4GB) - ~$30/month (wasteful)

Potential Savings: 50-75% reduction in compute costs.

---

#### 8. Why the Overestimation?

Likely reasons for inflated specs:

1. Legacy from Airflow: The project previously used Apache Airflow, which is much heavier. Airflow requires a webserver, scheduler, metadata DB, Redis/Celery, and a larger memory footprint. The `DEPLOYMENT_READINESS_REPORT.md` confirms Airflow was recently replaced.
2. Conservative Estimates: Copy-pasted from generic deployment guides.
3. No Profiling: Specs likely set before measuring actual resource usage.
4. Confusion: Frontend mentioned but deployed on Vercel, not EC2.

---

#### 9. Validation Recommendation

Before downsizing, I recommend:

1. Deploy to stated "minimum" first (2 vCPU, 4GB RAM)
2. Monitor for 1-2 weeks using CloudWatch metrics: CPU utilization, memory utilization, disk I/O
3. Analyze actual usage and right-size accordingly
4. Test ETL runs under load (manual trigger + API traffic)

---

### Final Verdict

The stated requirements are not justified for the actual workload.

- Minimum (2 vCPU, 4GB): Acceptable but wasteful (50-75% over-provisioned)
- Recommended (4 vCPU, 8GB): Completely unnecessary (75-85% over-provisioned)
- Optimal: 1-2 vCPU, 2GB RAM, 15GB storage

The project would run comfortably on half the "minimum" specification stated in this file.

## Step 1: Prepare EC2 Instance

### 1.1 Connect to your EC2 instance
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### 1.2 Update system packages
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install Docker and Docker Compose
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and log back in for group changes to take effect
exit
```

## Step 2: Clone and Setup Project

### 2.1 Clone the repository
```bash
git clone <your-repo-url> israel-flights-etl
cd israel-flights-etl
```

### 2.2 Create production environment file
```bash
cp .env.prod.example .env.prod
nano .env.prod  # or use your preferred editor
```

### 2.3 Update .env.prod with your values

**Important configurations for EC2:**

1. **Update CORS_ORIGINS** to allow your frontend domain:
   ```bash
   # Add your Vercel frontend domain
   CORS_ORIGINS=https://your-app.vercel.app
   ```

2. **Update database passwords** (use strong passwords in production):
   ```bash
   POSTGRES_FLIGHTS_PASSWORD=your_strong_password_here
   ```

3. **Update AWS credentials** (if using S3 for backups):
   ```bash
   AWS_ACCESS_KEY_ID=your_actual_key
   AWS_SECRET_ACCESS_KEY=your_actual_secret
   AWS_DEFAULT_REGION=us-east-1
   ```

4. **Configure ETL schedule** (optional, defaults to 15 minutes):
   ```bash
   SCHEDULE_INTERVAL_MINUTES=15
   ```

5. **Configure CKAN API** (optional, has defaults):
   ```bash
   CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search
   CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5
   CKAN_BATCH_SIZE=1000
   ```

## Step 3: Deploy with Docker Compose

### 3.1 Build and start all services
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod up -d --build
```

This will:
- Build all Docker images
- Start PostgreSQL database
- Start ETL runner (scheduled data pipeline)
- Start Backend API

### 3.2 Check service status
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod ps
```

### 3.3 View logs
```bash
# All services
docker compose -f docker-compose-prod.yml --env-file .env.prod logs -f

# Specific service
docker compose -f docker-compose-prod.yml --env-file .env.prod logs -f backend
docker compose -f docker-compose-prod.yml --env-file .env.prod logs -f etl
```

## Step 4: Verify Deployment

### 4.1 Check service health
```bash
# Backend
curl http://localhost:8000/health
```

### 4.2 Access services

- **Frontend**: Hosted on Vercel (e.g., `https://your-app.vercel.app`)
- **Backend API**: `http://YOUR_EC2_PUBLIC_IP:8000`
- **API Docs**: `http://YOUR_EC2_PUBLIC_IP:8000/docs`

## Step 5: Frontend Deployment on Vercel

The frontend is deployed separately on Vercel for optimal performance and automatic scaling.

### 5.1 Prerequisites
- Vercel account (free tier available)
- GitHub repository connected to Vercel

### 5.2 Deploy to Vercel

1. **Connect your repository to Vercel:**
   - Go to https://vercel.com
   - Click "New Project"
   - Import your GitHub repository

2. **Configure environment variables in Vercel:**
   ```
   VITE_API_URL=http://YOUR_EC2_PUBLIC_IP:8000
   ```

3. **Deploy:**
   - Vercel will automatically build and deploy
   - Every push to `main` branch triggers a new deployment

4. **Update CORS on Backend:**
   - After getting your Vercel URL, update `.env.prod` on EC2:
   ```bash
   CORS_ORIGINS=https://your-app.vercel.app
   ```
   - Restart backend:
   ```bash
   docker compose -f docker-compose-prod.yml --env-file .env.prod restart backend
   ```

## Step 6: Configure Reverse Proxy (Optional but Recommended)

For production, use Nginx as a reverse proxy to add SSL and improve security:

### 6.1 Install Nginx
```bash
sudo apt install nginx -y
```

### 6.2 Create Nginx configuration
```bash
sudo nano /etc/nginx/sites-available/israel-flights
```

Add the following configuration:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    # Backend API
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6.3 Enable and restart Nginx
```bash
sudo ln -s /etc/nginx/sites-available/israel-flights /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 7: Set Up SSL with Let's Encrypt (Optional but Recommended)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

## Common Commands

### Stop all services
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod down
```

### Stop and remove volumes (WARNING: deletes data)
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod down -v
```

**Notes:**
- If you are using the default named volume for `postgres_flights`, this **permanently deletes the flights database data**.
- To make your DB survive `down -v`, set `POSTGRES_FLIGHTS_DATA_DIR` in your `.env` to an **absolute path** so Postgres uses a bind mount.
- If you must wipe volumes, take a backup first (`pg_dump`) and confirm you can restore it.

### Restart a specific service
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod restart backend
```

### View logs
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod logs -f [service_name]
```

### Execute commands in containers
```bash
# Access backend container
docker compose -f docker-compose-prod.yml --env-file .env.prod exec backend bash

# Access database
docker compose -f docker-compose-prod.yml --env-file .env.prod exec postgres_flights psql -U daniel flights_db
```

### Update and redeploy
```bash
git pull
docker compose -f docker-compose-prod.yml --env-file .env.prod up -d --build
```

## Troubleshooting

### Services won't start
1. Check logs: `docker compose logs`
2. Verify .env file is correct
3. Check port conflicts: `sudo netstat -tulpn | grep LISTEN`
4. Verify Docker is running: `sudo systemctl status docker`

### Database connection issues
1. Wait for database to be healthy: `docker compose ps`
2. Check database logs: `docker compose logs postgres_flights`
3. Verify credentials in .env match database configuration

### Backend can't connect to database
1. Check backend logs: `docker compose logs backend`
2. Verify DATABASE_URL in .env is correct
3. Ensure postgres_flights is healthy: `docker compose ps`

### ETL runner not fetching data
1. Check ETL logs: `docker compose logs etl`
2. Verify CKAN API credentials in .env
3. Test API manually: `curl "https://data.gov.il/api/3/action/datastore_search?resource_id=e83f763b-b7d7-479e-b172-ae981ddc6de5&limit=1"`

### Frontend can't connect to backend
1. Verify VITE_API_URL in Vercel environment variables
2. Check CORS settings in backend .env
3. Ensure backend is accessible: `curl http://YOUR_EC2_IP:8000/health`
4. Check security group rules allow port 8000

## Monitoring

### Resource usage
```bash
docker stats
```

### Disk usage
```bash
docker system df
```

### Clean up unused resources
```bash
docker system prune -a
```

## Backup

### Backup database
```bash
# Backup Flights database
docker compose -f docker-compose-prod.yml --env-file .env.prod exec postgres_flights pg_dump -U daniel flights_db > flights_backup.sql
```

### Restore database
```bash
# Restore Flights database
cat flights_backup.sql | docker compose -f docker-compose-prod.yml --env-file .env.prod exec -T postgres_flights psql -U daniel flights_db
```

## Security Considerations

1. **Change all default passwords** in .env file
2. **Use strong passwords** for databases
3. **Enable SSL/TLS** for production (use Let's Encrypt)
4. **Regularly update** Docker images and system packages
5. **Monitor logs** for suspicious activity
6. **Backup databases** regularly
7. **Use AWS IAM roles** instead of access keys when possible
8. **Restrict backend API access** with security groups
9. **Use environment variables** for all sensitive data

## Architecture Notes

- **No Airflow**: This project uses a lightweight Python scheduler (APScheduler) instead of Apache Airflow
- **Lightweight ETL**: The ETL runner is a simple Python script that runs on a schedule
- **Vercel Frontend**: Frontend is deployed on Vercel for optimal CDN performance and automatic scaling
- **Docker Compose**: All backend services run in Docker containers on a single EC2 instance

## Support

For issues or questions, check the project documentation or create an issue in the repository.
