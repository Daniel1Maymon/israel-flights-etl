# Railway Private Networking Setup Guide

This guide explains how to set up Railway Private Networking so your ETL service can communicate with your Backend service securely using Railway's internal network.

## Architecture Overview

```
┌─────────────────┐      Private Network      ┌──────────────────┐
│   ETL Service   │ ────────────────────────> │  Backend Service │
│   (Railway)     │  http://backend.railway.  │    (Railway)     │
└─────────────────┘        internal:8000      └──────────────────┘
                                                        │
                                                        │ Public HTTPS
                                                        ▼
                                              ┌──────────────────┐
                                              │  Frontend (Vercel)│
                                              └──────────────────┘
```

## Step 1: Deploy Backend Service to Railway

### 1.1 Create Backend Service
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will auto-detect the `backend/Dockerfile.railway`

### 1.2 Configure Backend Service
1. Click on your backend service
2. Go to **Settings** tab
3. Set **Service Name**: `backend` (important for private networking)
4. Set **Root Directory**: `/backend`
5. Set **Dockerfile Path**: `Dockerfile.railway`

### 1.3 Get Backend Private Domain
1. In your backend service, go to **Settings** tab
2. Scroll to **Networking** section
3. You'll see **Private Networking** enabled automatically
4. Note the **Private Domain**: `backend.railway.internal`
5. Note the **PORT** Railway assigns (usually `8000` but can vary)

The backend's private URL will be:
```
http://backend.railway.internal:$PORT
```

### 1.4 Set Backend Environment Variables
In the backend service, go to **Variables** tab and add:

```bash
# Database (Railway will auto-inject if using Railway Postgres)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# CORS - Add your Vercel frontend URL
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-preview.vercel.app

# API Settings
LOG_LEVEL=INFO
```

**Important**: Replace `https://your-app.vercel.app` with your actual Vercel deployment URL.

## Step 2: Deploy ETL Service to Railway

### 2.1 Create ETL Service
1. In the same Railway project, click **"New Service"**
2. Select **"GitHub Repo"** → Choose the same repository
3. Railway will create a second service

### 2.2 Configure ETL Service
1. Click on your ETL service
2. Go to **Settings** tab
3. Set **Service Name**: `etl-runner`
4. Set **Root Directory**: `/etl`
5. Set **Dockerfile Path**: `Dockerfile.railway`

### 2.3 Link ETL to Backend via Private Networking

In the ETL service, go to **Variables** tab and add:

```bash
# Database (use same as backend)
DATABASE_URL=${{backend.DATABASE_URL}}

# Backend Private URL - This enables ETL → Backend communication
BACKEND_PRIVATE_URL=http://backend.railway.internal:8000

# ETL Configuration
SCHEDULE_INTERVAL_MINUTES=15
CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search
CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5
CKAN_BATCH_SIZE=1000

# Logging
LOG_LEVEL=INFO
```

### 2.4 Reference Backend Variables (Optional)
Railway allows you to reference variables from other services:

```bash
# Reference backend's database URL
DATABASE_URL=${{backend.DATABASE_URL}}

# Or if backend has a specific variable
BACKEND_API_KEY=${{backend.API_KEY}}
```

## Step 3: Deploy Database (PostgreSQL)

### 3.1 Add Railway Postgres
1. In your Railway project, click **"New Service"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will provision a Postgres instance

### 3.2 Connect Services to Database
Railway automatically injects `DATABASE_URL` into services. To manually reference:

**Backend Variables:**
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**ETL Variables:**
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

## Step 4: Verify Private Networking

### 4.1 Check Backend Service Logs
Deploy your backend and check logs:
```bash
# You should see:
Starting Israel Flights API
Application startup complete
```

### 4.2 Check ETL Service Logs
Deploy your ETL and check logs:
```bash
# You should see:
Backend client initialized with URL: http://backend.railway.internal:8000
Starting ETL pipeline run
```

### 4.3 Test Private Network Communication
The ETL service can now communicate with backend using:
```python
import os
import requests

backend_url = os.getenv("BACKEND_PRIVATE_URL")
# backend_url = "http://backend.railway.internal:8000"

# Health check
response = requests.get(f"{backend_url}/health")
print(response.json())  # Should return healthy status
```

## Step 5: Deploy Frontend to Vercel

### 5.1 Set Backend URL in Vercel
1. Go to Vercel Dashboard → Your project
2. Go to **Settings** → **Environment Variables**
3. Add:
   ```bash
   NEXT_PUBLIC_API_URL=https://your-backend.railway.app
   ```

### 5.2 Update Backend CORS
In Railway backend service, update `CORS_ORIGINS` variable:
```bash
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-preview.vercel.app
```

**Important**: Include both production and preview URLs if needed.

## Railway Private Networking Details

### How It Works
- Railway creates an internal network for all services in a project
- Services can communicate using `<service-name>.railway.internal`
- Private network traffic is free and faster than public internet
- No need to expose ports publicly for internal communication

### Private Domain Format
```
http://<service-name>.railway.internal:<port>
```

Examples:
- `http://backend.railway.internal:8000`
- `http://api.railway.internal:3000`
- `http://etl-runner.railway.internal:5000`

### Best Practices

1. **Use Private URLs for Internal Communication**
   - ETL → Backend: Use private URL
   - Backend → Database: Automatically handled by Railway

2. **Use Public URLs for External Access**
   - Frontend → Backend: Use public Railway URL (`*.railway.app`)
   - External APIs → Backend: Use public Railway URL

3. **Security**
   - Private network traffic is isolated to your Railway project
   - No internet exposure for internal services
   - Use environment variables for sensitive data

4. **Variable References**
   - Use `${{service.VARIABLE}}` to reference other service variables
   - Automatically updates when source variable changes
   - Useful for shared database URLs

## Troubleshooting

### ETL Cannot Reach Backend
**Symptom**: ETL logs show connection errors to backend

**Solutions**:
1. Verify backend service name is exactly `backend` (check Settings → Service Name)
2. Verify `BACKEND_PRIVATE_URL` is set correctly in ETL variables
3. Check backend is running and healthy (view logs)
4. Verify PORT in private URL matches backend's PORT (usually 8000)

### CORS Errors from Frontend
**Symptom**: Browser console shows CORS errors

**Solutions**:
1. Verify `CORS_ORIGINS` in backend includes your Vercel URL
2. Include both `https://your-app.vercel.app` and preview URLs
3. Check backend logs for CORS middleware initialization
4. Ensure URLs don't have trailing slashes

### Database Connection Issues
**Symptom**: Services cannot connect to database

**Solutions**:
1. Verify `DATABASE_URL` is set in both services
2. Check Railway Postgres is running (green indicator)
3. Use Railway's provided `DATABASE_URL` format
4. Verify connection string includes correct credentials

### Private Network Not Working
**Symptom**: Services cannot reach each other via `.railway.internal`

**Solutions**:
1. Ensure both services are in the same Railway project
2. Verify service names match exactly (case-sensitive)
3. Check both services are deployed and running
4. Railway private networking is automatic - no configuration needed

## Testing Private Networking

### Test Backend Health from ETL
Add this to your ETL code:
```python
from etl.backend_client import BackendClient
from etl.config import get_config

config = get_config()
client = BackendClient(config["backend_url"])

if client.health_check():
    print("✅ Backend is reachable via private network")
else:
    print("❌ Backend is not reachable")
```

### Test Database from Both Services
Both backend and ETL should successfully connect to Postgres:
```python
import psycopg
import os

database_url = os.getenv("DATABASE_URL")
try:
    conn = psycopg.connect(database_url)
    print("✅ Database connected")
    conn.close()
except Exception as e:
    print(f"❌ Database connection failed: {e}")
```

## Complete Environment Variable Reference

### Backend Service Variables
```bash
# Database
DATABASE_URL=${{Postgres.DATABASE_URL}}

# CORS for Vercel Frontend
CORS_ORIGINS=https://your-app.vercel.app,https://preview-*.vercel.app

# API Settings
API_HOST=0.0.0.0
LOG_LEVEL=INFO

# Security (optional)
SECRET_KEY=your-secret-key-change-in-production
```

### ETL Service Variables
```bash
# Database (shared with backend)
DATABASE_URL=${{backend.DATABASE_URL}}

# Backend Private Network URL
BACKEND_PRIVATE_URL=http://backend.railway.internal:8000

# ETL Configuration
SCHEDULE_INTERVAL_MINUTES=15
CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search
CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5
CKAN_BATCH_SIZE=1000
LOG_LEVEL=INFO
```

### Frontend (Vercel) Variables
```bash
# Backend Public URL (NOT private URL)
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

## Summary

✅ **Backend Service**: Exposes public API for frontend, private network for ETL
✅ **ETL Service**: Uses private network to communicate with backend
✅ **Frontend (Vercel)**: Uses public backend URL
✅ **Database**: Shared by backend and ETL via `DATABASE_URL`
✅ **CORS**: Backend allows requests from Vercel frontend
✅ **Security**: Private network traffic isolated within Railway project

Your services are now connected securely using Railway Private Networking! 🚀
