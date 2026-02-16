# 🚀 Quick Deployment Guide - Railway + Vercel

Deploy your Israel Flights ETL system publicly in ~15 minutes!

## Overview

- **Database + Backend + ETL**: Railway (Free tier: $5 credit/month)
- **Frontend**: Vercel (Free tier available)
- **Cost**: Free to start, ~$5-10/month after free credits

---

## Step 1: Make Repository Public (Optional)

If you want to make your GitHub repository public:

1. Go to: https://github.com/Daniel1Maymon/israel-flights-etl
2. Click **Settings** (top-right)
3. Scroll to the bottom → **Danger Zone**
4. Click **Change visibility** → **Make public**
5. Confirm the action

---

## Step 2: Deploy Database on Railway

### 2.1 Create PostgreSQL Database

1. **Sign up/Login to Railway**: https://railway.app
2. Click **"New Project"**
3. Select **"Deploy PostgreSQL"**
4. Wait for deployment (1-2 minutes)
5. **Copy the connection details** (you'll need them later):
   - Click on the PostgreSQL service
   - Go to **"Variables"** tab
   - Note these values:
     - `PGHOST`
     - `PGPORT`
     - `PGUSER`
     - `PGPASSWORD`
     - `PGDATABASE`

---

## Step 3: Deploy Backend on Railway

### 3.1 Deploy Backend Service

1. In the same Railway project, click **"New Service"**
2. Select **"GitHub Repo"**
3. Authorize Railway to access your GitHub
4. Select your repository: `israel-flights-etl`
5. Railway will auto-detect the project

### 3.2 Configure Backend Build Settings

1. Click on the newly created service
2. Go to **"Settings"** tab
3. Set the following:
   - **Root Directory**: `backend`
   - **Dockerfile Path**: `Dockerfile.railway`
4. Click **"Deploy"**

### 3.3 Set Backend Environment Variables

Go to the **"Variables"** tab and add these variables:

```bash
# Database Connection (use values from Step 2.1)
DATABASE_URL=postgresql://<PGUSER>:<PGPASSWORD>@<PGHOST>:<PGPORT>/<PGDATABASE>
DB_HOST=<PGHOST from PostgreSQL service>
DB_PORT=<PGPORT from PostgreSQL service>
DB_NAME=<PGDATABASE from PostgreSQL service>
DB_USER=<PGUSER from PostgreSQL service>
DB_PASSWORD=<PGPASSWORD from PostgreSQL service>

# Application Settings
LOG_LEVEL=INFO
CORS_ORIGINS=*

# Railway will automatically provide PORT variable
```

**Tip**: Railway can auto-link services! Click "**+ New Variable**" → "**Add reference**" → Select your PostgreSQL service variables.

### 3.4 Get Backend URL

1. Go to **"Settings"** tab
2. Scroll to **"Networking"**
3. Click **"Generate Domain"**
4. Copy the URL (e.g., `https://your-backend-xxx.up.railway.app`)
5. **Save this URL** - you'll need it for the frontend!

---

## Step 4: Deploy ETL Service on Railway

### 4.1 Create ETL Service

1. In the same Railway project, click **"New Service"** again
2. Select **"GitHub Repo"**
3. Select the same repository: `israel-flights-etl`

### 4.2 Configure ETL Build Settings

1. Click on the ETL service
2. Go to **"Settings"** tab
3. Set the following:
   - **Root Directory**: `etl`
   - **Dockerfile Path**: `Dockerfile.railway`
4. Click **"Deploy"**

### 4.3 Set ETL Environment Variables

Go to the **"Variables"** tab and add these:

```bash
# Database Connection (reference PostgreSQL service)
POSTGRES_FLIGHTS_HOST=<PGHOST from PostgreSQL service>
POSTGRES_FLIGHTS_PORT=<PGPORT from PostgreSQL service>
POSTGRES_FLIGHTS_DB=<PGDATABASE from PostgreSQL service>
POSTGRES_FLIGHTS_USER=<PGUSER from PostgreSQL service>
POSTGRES_FLIGHTS_PASSWORD=<PGPASSWORD from PostgreSQL service>

# ETL Configuration
SCHEDULE_INTERVAL_MINUTES=15

# CKAN API (optional - has defaults)
CKAN_BASE_URL=https://data.gov.il/api/3/action/datastore_search
CKAN_RESOURCE_ID=e83f763b-b7d7-479e-b172-ae981ddc6de5
CKAN_BATCH_SIZE=1000

# Backend API URL (for Railway Private Networking)
BACKEND_PRIVATE_URL=<your-backend-service-name>.railway.internal:8000
```

**Important**: Replace `<your-backend-service-name>` with the actual Railway service name of your backend (you can find it in the service settings).

---

## Step 5: Deploy Frontend on Vercel

### 5.1 Deploy to Vercel

1. **Sign up/Login to Vercel**: https://vercel.com
2. Click **"Add New Project"**
3. **Import Git Repository**:
   - Select your repository: `israel-flights-etl`
   - Authorize Vercel to access GitHub if needed
4. **Configure Project**:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` (should be auto-detected)
   - **Output Directory**: `dist` (should be auto-detected)
5. Click **"Deploy"**

### 5.2 Set Frontend Environment Variables

After deployment, configure environment variables:

1. Go to your project in Vercel
2. Click **"Settings"** → **"Environment Variables"**
3. Add this variable:

```bash
VITE_API_URL=<your-backend-url-from-step-3.4>
```

**Example**:
```bash
VITE_API_URL=https://your-backend-xxx.up.railway.app
```

4. Click **"Save"**
5. Go to **"Deployments"** tab
6. Click **"Redeploy"** (to apply the new environment variable)

### 5.3 Update Backend CORS

Now that you have your Vercel URL, update the backend CORS settings:

1. Go back to **Railway**
2. Click on your **Backend service**
3. Go to **"Variables"** tab
4. Update the `CORS_ORIGINS` variable:

```bash
CORS_ORIGINS=https://your-frontend-xxx.vercel.app
```

**Tip**: You can use `*` for development, but use specific domains for production security.

5. Save and redeploy the backend

---

## Step 6: Verify Deployment

### 6.1 Test Backend

Visit your backend URL with `/health` endpoint:
```
https://your-backend-xxx.up.railway.app/health
```

You should see: `{"status": "healthy"}` or similar.

### 6.2 Test API Documentation

Visit:
```
https://your-backend-xxx.up.railway.app/docs
```

You should see the interactive API documentation (Swagger UI).

### 6.3 Test Frontend

Visit your Vercel URL:
```
https://your-frontend-xxx.vercel.app
```

The dashboard should load and display flight data!

### 6.4 Check ETL Logs

1. Go to **Railway**
2. Click on your **ETL service**
3. Go to **"Logs"** tab
4. You should see the ETL scheduler running every 15 minutes
5. Look for messages like: `"ETL run completed successfully"`

---

## Step 7: Monitor & Maintain

### Railway Dashboard

- **View Logs**: Click on any service → "Logs" tab
- **Monitor Resource Usage**: Check the "Metrics" tab
- **Restart Services**: Go to "Deployments" → Click "Restart"

### Vercel Dashboard

- **View Deployments**: See all deployments and their status
- **Check Logs**: Click on a deployment → "Logs" tab
- **Automatic Deployments**: Every push to `main` branch triggers a new deployment

---

## Common Issues & Solutions

### Issue 1: Backend Can't Connect to Database

**Solution**:
1. Verify PostgreSQL service is running on Railway
2. Check that backend environment variables match PostgreSQL credentials
3. Use Railway's **variable references** instead of hardcoding values

### Issue 2: Frontend Shows "Network Error"

**Solution**:
1. Check that `VITE_API_URL` in Vercel points to the correct Railway backend URL
2. Verify `CORS_ORIGINS` in Railway backend includes your Vercel URL
3. Make sure backend is running (check Railway logs)

### Issue 3: ETL Not Fetching Data

**Solution**:
1. Check ETL service logs on Railway
2. Verify database credentials are correct
3. Test the CKAN API manually:
```bash
curl "https://data.gov.il/api/3/action/datastore_search?resource_id=e83f763b-b7d7-479e-b172-ae981ddc6de5&limit=1"
```

### Issue 4: Railway Services Crashing

**Solution**:
1. Check service logs for error messages
2. Verify all environment variables are set correctly
3. Check that Dockerfile paths are correct in settings
4. Ensure PostgreSQL is healthy before backend/ETL start

---

## Cost Breakdown

### Railway (Backend + Database + ETL)

- **Free Trial**: $5 credit/month
- **After Free Trial**:
  - PostgreSQL: ~$2-3/month
  - Backend: ~$2-3/month
  - ETL: ~$1-2/month
- **Total**: ~$5-8/month

### Vercel (Frontend)

- **Free Tier**:
  - 100 GB bandwidth/month
  - Unlimited deployments
  - Custom domains included
- **After Free Tier**: Hobby plan at $20/month (but free tier is usually sufficient)

**Total Monthly Cost**: $5-8 for Railway, $0 for Vercel = **$5-8/month**

---

## Next Steps

### 1. Custom Domain (Optional)

**Vercel**:
1. Go to project settings → "Domains"
2. Add your custom domain
3. Follow DNS configuration instructions

**Railway**:
1. Go to service settings → "Networking"
2. Add custom domain
3. Update DNS records

### 2. Enable HTTPS (Already Included!)

Both Railway and Vercel provide **automatic HTTPS** with SSL certificates. No additional configuration needed!

### 3. Set Up Monitoring

**Railway**:
- Use built-in metrics and logs
- Set up email notifications for service failures

**Vercel**:
- Use Vercel Analytics (free)
- Set up deployment notifications

### 4. Configure Backups

Add to your ETL environment variables on Railway:

```bash
# AWS S3 Backups (optional)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
ENABLE_DB_BACKUPS=true
S3_BUCKET_NAME=your-bucket-name
```

---

## Security Best Practices

1. **Never commit sensitive data** (API keys, passwords) to Git
2. **Use environment variables** for all configuration
3. **Update dependencies regularly**:
   - Frontend: `cd frontend && npm update`
   - Backend: `cd backend && pip install --upgrade -r requirements.txt`
4. **Enable 2FA** on Railway and Vercel accounts
5. **Restrict CORS origins** to your specific domains (not `*`)
6. **Monitor logs** for suspicious activity

---

## Useful Commands

### Update Your Deployment

```bash
# Make changes to your code
git add .
git commit -m "Your changes"
git push origin main

# Railway and Vercel will auto-deploy!
```

### Manual Deployment

**Railway**: Go to service → "Deployments" → Click "Redeploy"
**Vercel**: Go to project → "Deployments" → Click "Redeploy"

---

## Support & Resources

- **Railway Docs**: https://docs.railway.app
- **Vercel Docs**: https://vercel.com/docs
- **Project Documentation**: See `/docs` folder in repository
- **API Documentation**: `https://your-backend-url.up.railway.app/docs`

---

## Congratulations! 🎉

Your Israel Flights ETL system is now live and publicly accessible!

- **Frontend**: https://your-frontend-xxx.vercel.app
- **Backend API**: https://your-backend-xxx.up.railway.app
- **API Docs**: https://your-backend-xxx.up.railway.app/docs

Share your deployment URLs and showcase your project to the world! 🚀
