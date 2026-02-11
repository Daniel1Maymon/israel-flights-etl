# Railway Deployment Quickstart Guide

This guide provides the fastest path to deploy your Israel Flights ETL system to Railway with Private Networking.

## 🎯 Deployment Overview

```
┌─────────────┐         Private Network          ┌─────────────┐
│ ETL Service │ ─────────────────────────────>   │   Backend   │
│  (Railway)  │  http://backend.railway.internal │  (Railway)  │
└─────────────┘                                   └─────────────┘
                                                         │
                                                         │ Public HTTPS
                                                         ▼
                                                  ┌─────────────┐
                                                  │  Frontend   │
                                                  │  (Vercel)   │
                                                  └─────────────┘
```

---

## 📦 Step 1: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your repository

---

## 🗄️ Step 2: Add PostgreSQL Database

1. In your Railway project, click **"New Service"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will provision a Postgres instance
4. Note: `DATABASE_URL` will be auto-injected into other services

---

## 🚀 Step 3: Deploy Backend Service

### Create Service
1. Click **"New Service"** → **"GitHub Repo"**
2. Select your repository

### Configure Service
1. Go to **Settings** tab:
   - **Service Name**: `backend` (important!)
   - **Root Directory**: `backend`
   - **Dockerfile Path**: `Dockerfile.railway`

### Set Environment Variables
Go to **Variables** tab and add:

```bash
# Database (reference Postgres service)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# CORS - Replace with YOUR Vercel URL
CORS_ORIGINS=https://your-app.vercel.app

# Optional settings
LOG_LEVEL=INFO
```

### Get Private Domain
1. Go to **Settings** → **Networking**
2. Note the **Private Domain**: `backend.railway.internal`
3. This is used by ETL service for internal communication

---

## ⚙️ Step 4: Deploy ETL Service

### Create Service
1. Click **"New Service"** → **"GitHub Repo"**
2. Select the same repository

### Configure Service
1. Go to **Settings** tab:
   - **Service Name**: `etl-runner`
   - **Root Directory**: `etl`
   - **Dockerfile Path**: `Dockerfile.railway`

### Set Environment Variables
Go to **Variables** tab and add:

```bash
# Database (reference backend or Postgres)
DATABASE_URL=${{backend.DATABASE_URL}}

# 🔑 CRITICAL: Backend Private URL for Railway Private Networking
BACKEND_PRIVATE_URL=http://backend.railway.internal:8000

# ETL Configuration
SCHEDULE_INTERVAL_MINUTES=15
CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search
CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5
CKAN_BATCH_SIZE=1000

# Logging
LOG_LEVEL=INFO
```

**Important**: The `BACKEND_PRIVATE_URL` enables ETL to communicate with Backend via Railway's internal network.

---

## 🌐 Step 5: Deploy Frontend to Vercel

### Connect Repository
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **"New Project"** → Select your repository
3. Set **Root Directory**: `/frontend`

### Set Environment Variables
In Vercel Settings → Environment Variables:

```bash
# Backend PUBLIC URL (get from Railway backend service)
NEXT_PUBLIC_API_URL=https://your-backend-name.railway.app
```

**Note**: Use the **public** Railway URL, not the private `.railway.internal` URL.

### Deploy
1. Click **"Deploy"**
2. Copy the production URL (e.g., `https://your-app.vercel.app`)

---

## 🔧 Step 6: Update Backend CORS

1. Go back to Railway → **Backend Service** → **Variables**
2. Update `CORS_ORIGINS` with your Vercel URL:

```bash
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-git-*.vercel.app
```

3. Include preview URLs for branch deployments if needed

---

## ✅ Step 7: Verify Deployment

### Check Backend
1. Go to Railway → Backend Service → **Deployments**
2. Click on latest deployment to view logs
3. Look for:
   ```
   Starting Israel Flights API
   Application startup complete
   ```

### Check ETL
1. Go to Railway → ETL Service → **Deployments**
2. View logs for:
   ```
   Backend client initialized with URL: http://backend.railway.internal:8000
   Starting ETL pipeline run
   Pipeline complete — X rows upserted
   ```

### Check Frontend
1. Open your Vercel URL in browser
2. Open Developer Console → Network tab
3. Verify requests to backend succeed (no CORS errors)

---

## 🔍 Testing Private Networking

### Test 1: Backend Health from ETL
SSH into ETL service (Railway CLI) and run:
```bash
curl http://backend.railway.internal:8000/health
```

Expected output:
```json
{"status": "healthy", "database": "connected"}
```

### Test 2: Database Connection
Both services should connect successfully:
```bash
# Check backend logs
[INFO] Database connection successful

# Check ETL logs
[INFO] Connected to database: postgres.railway.internal
[INFO] Pipeline complete — 1234 rows upserted
```

### Test 3: Frontend to Backend
Open your Vercel app and check:
- Data loads correctly
- No CORS errors in console
- API requests succeed

---

## 📋 Environment Variables Checklist

### Backend Service (`backend`)
- [x] `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- [x] `CORS_ORIGINS=https://your-app.vercel.app`
- [x] `LOG_LEVEL=INFO`

### ETL Service (`etl-runner`)
- [x] `DATABASE_URL=${{backend.DATABASE_URL}}`
- [x] `BACKEND_PRIVATE_URL=http://backend.railway.internal:8000`
- [x] `SCHEDULE_INTERVAL_MINUTES=15`
- [x] `CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search`
- [x] `CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5`
- [x] `LOG_LEVEL=INFO`

### Frontend (Vercel)
- [x] `NEXT_PUBLIC_API_URL=https://your-backend.railway.app`

---

## 🐛 Troubleshooting

### ETL Cannot Reach Backend
**Error**: `Backend unreachable: Connection refused`

**Solution**:
1. Verify backend service name is exactly `backend`
2. Check `BACKEND_PRIVATE_URL=http://backend.railway.internal:8000`
3. Ensure backend is deployed and running

### CORS Errors
**Error**: `Access to fetch at ... has been blocked by CORS policy`

**Solution**:
1. Update `CORS_ORIGINS` in backend service
2. Include your exact Vercel URL (no trailing slash)
3. Redeploy backend service

### Database Connection Failed
**Error**: `Database connection failed`

**Solution**:
1. Verify Postgres service is running (green indicator)
2. Check `DATABASE_URL` is set correctly
3. Ensure both services reference same database

### Backend Not Healthy
**Error**: `Backend health check failed`

**Solution**:
1. Check backend logs for errors
2. Verify `DATABASE_URL` is set correctly
3. Ensure backend service deployed successfully

---

## 🎉 Success Indicators

Your deployment is successful when:

✅ **Backend Service**
- Health endpoint returns 200 OK
- Logs show "Application startup complete"
- Database connection successful

✅ **ETL Service**
- Logs show backend URL configured
- Pipeline runs complete successfully
- Database records being upserted

✅ **Frontend**
- Opens without errors
- Displays data from backend API
- No CORS errors in console

✅ **Private Networking**
- ETL can reach backend via `.railway.internal`
- Backend health check succeeds from ETL
- No public internet used for internal communication

---

## 🔗 Important URLs

After deployment, save these URLs:

| Service | URL Type | Example | Used By |
|---------|----------|---------|---------|
| Backend | Public | `https://backend-abc123.railway.app` | Frontend (Vercel) |
| Backend | Private | `http://backend.railway.internal:8000` | ETL Service |
| Frontend | Public | `https://your-app.vercel.app` | End Users |
| Database | Private | Auto-injected by Railway | Backend & ETL |

---

## 📚 Additional Resources

- **Detailed Guide**: See `RAILWAY_PRIVATE_NETWORKING_GUIDE.md`
- **Python Examples**: See `RAILWAY_PYTHON_EXAMPLES.md`
- **Railway Docs**: https://docs.railway.app/reference/private-networking
- **Vercel Docs**: https://vercel.com/docs/concepts/deployments/overview

---

## 🚨 Security Best Practices

1. **Never expose private URLs publicly**
   - Use `.railway.internal` only between Railway services
   - Use public URLs (`*.railway.app`) for external access

2. **Secure environment variables**
   - Never commit `.env` files to git
   - Use Railway's Variables UI for secrets
   - Rotate credentials regularly

3. **CORS configuration**
   - Only allow specific frontend URLs
   - Never use `*` in production
   - Include preview URLs for testing

4. **Database access**
   - Only expose database to Railway services
   - Use strong passwords (Railway generates these)
   - Enable SSL connections (automatic on Railway)

---

## 🎯 Next Steps

After successful deployment:

1. **Monitor Services**: Check Railway dashboard for service health
2. **Set Up Alerts**: Configure Railway notifications for failures
3. **Add Logging**: Use Railway logs for debugging
4. **Enable Metrics**: Monitor resource usage and performance
5. **Backup Database**: Set up automated backups via Railway

---

## 💡 Tips

- **Use Railway CLI** for faster debugging and log access
- **Reference variables** across services: `${{service.VARIABLE}}`
- **Preview deployments** automatically work with Railway
- **Environment separation**: Create separate projects for staging/production
- **Cost optimization**: Railway's private networking is free (saves bandwidth)

---

Congratulations! Your Israel Flights ETL system is now deployed on Railway with secure Private Networking! 🎉
