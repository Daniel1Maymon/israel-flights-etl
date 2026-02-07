# Deployment Guide for EC2

This guide will help you deploy the Israel Flights ETL project on an EC2 instance using Docker Compose.

## Prerequisites

1. **EC2 Instance** (Ubuntu 22.04 LTS recommended)
   - Minimum: 2 vCPU, 4GB RAM
   - Recommended: 4 vCPU, 8GB RAM
   - At least 20GB storage

2. **Security Group Configuration**
   - Open port 80 (HTTP) for frontend only if hosting frontend on this server
   - Open port 8000 (Backend API) - optional if using reverse proxy
   - Open port 8082 (Airflow Web UI) - optional
   - Open port 22 (SSH) for access

3. **AWS Credentials** (if using S3)
   - AWS Access Key ID
   - AWS Secret Access Key
   - IAM permissions for S3 access

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
   # Add your frontend domain
   CORS_ORIGINS=https://israel-flights-pxuqv4mj1-daniel1maymons-projects.vercel.app
   ```

2. **Update database passwords** (use strong passwords in production):
   ```bash
   POSTGRES_AIRFLOW_PASSWORD=your_strong_password_here
   POSTGRES_FLIGHTS_PASSWORD=your_strong_password_here
   ```

3. **Update AWS credentials** (if using S3):
   ```bash
   AWS_ACCESS_KEY_ID=your_actual_key
   AWS_SECRET_ACCESS_KEY=your_actual_secret
   AWS_DEFAULT_REGION=us-east-1
   ```

4. **Update Airflow credentials**:
   ```bash
   AIRFLOW_USERNAME=admin
   AIRFLOW_PASSWORD=your_strong_password_here
   ```

## Step 3: Deploy with Docker Compose

### 3.1 Build and start all services
```bash
docker compose -f docker-compose-prod.yml --env-file .env.prod up -d --build
```

This will:
- Build all Docker images
- Start PostgreSQL databases
- Initialize Airflow
- Start Airflow webserver and scheduler
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
docker compose -f docker-compose-prod.yml --env-file .env.prod logs -f airflow-webserver
```

## Step 4: Verify Deployment

### 4.1 Check service health
```bash
# Frontend
curl http://localhost/health

# Backend
curl http://localhost:8000/health

# Airflow
curl http://localhost:8082/health
```

### 4.2 Access services

- **Frontend**: Hosted on Vercel
- **Backend API**: `http://YOUR_EC2_PUBLIC_IP:8000`
- **API Docs**: `http://YOUR_EC2_PUBLIC_IP:8000/docs`
- **Airflow UI**: `http://YOUR_EC2_PUBLIC_IP:8082`
  - Username: (from AIRFLOW_USERNAME in .env)
  - Password: (from AIRFLOW_PASSWORD in .env)

## Step 5: Configure Reverse Proxy (Optional but Recommended)

For production, use Nginx as a reverse proxy:

### 5.1 Install Nginx
```bash
sudo apt install nginx -y
```

### 5.2 Create Nginx configuration
```bash
sudo nano /etc/nginx/sites-available/israel-flights
```

Add the following configuration:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Airflow
    location /airflow {
        proxy_pass http://localhost:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5.3 Enable and restart Nginx
```bash
sudo ln -s /etc/nginx/sites-available/israel-flights /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 6: Set Up SSL with Let's Encrypt (Optional)

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

Notes:
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

# Access Airflow container
docker compose -f docker-compose-prod.yml --env-file .env.prod exec airflow-webserver bash

# Run database migrations
docker compose -f docker-compose-prod.yml --env-file .env.prod exec backend alembic upgrade head
```

### Update and redeploy
```bash
git pull
docker compose -f docker-compose-prod.yml --env-file .env.prod up -d --build
```

## Troubleshooting

### Services won't start
1. Check logs: `docker-compose logs`
2. Verify .env file is correct
3. Check port conflicts: `sudo netstat -tulpn | grep LISTEN`
4. Verify Docker is running: `sudo systemctl status docker`

### Database connection issues
1. Wait for databases to be healthy: `docker-compose ps`
2. Check database logs: `docker-compose logs postgres_flights`
3. Verify credentials in .env match database configuration

### Frontend can't connect to backend
1. Verify VITE_API_URL in .env is correct
2. Rebuild frontend: `docker-compose up -d --build frontend`
3. Check backend is running: `curl http://localhost:8000/health`
4. Check CORS settings in backend/config.py

### Airflow initialization fails
1. Check Airflow init logs: `docker-compose logs airflow-init`
2. Verify database connections
3. Remove and recreate: `docker-compose down && docker-compose up -d`

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

### Backup databases
```bash
# Backup Airflow database
docker compose -f docker-compose-prod.yml --env-file .env.prod exec postgres_airflow pg_dump -U postgres airflow > airflow_backup.sql

# Backup Flights database
docker compose -f docker-compose-prod.yml --env-file .env.prod exec postgres_flights pg_dump -U daniel flights_db > flights_backup.sql
```

### Restore databases
```bash
# Restore Airflow database
cat airflow_backup.sql | docker compose -f docker-compose-prod.yml --env-file .env.prod exec -T postgres_airflow psql -U postgres airflow

# Restore Flights database
cat flights_backup.sql | docker compose -f docker-compose-prod.yml --env-file .env.prod exec -T postgres_flights psql -U daniel flights_db
```

## Security Considerations

1. **Change all default passwords** in .env file
2. **Use strong passwords** for databases and Airflow
3. **Restrict access** to Airflow UI (consider VPN or IP whitelist)
4. **Enable SSL/TLS** for production
5. **Regularly update** Docker images and system packages
6. **Monitor logs** for suspicious activity
7. **Backup databases** regularly
8. **Use AWS IAM roles** instead of access keys when possible

## Support

For issues or questions, check the project documentation or create an issue in the repository.
