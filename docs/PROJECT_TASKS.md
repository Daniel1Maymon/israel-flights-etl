# Israel Flights ETL – Project Tasks (Updated by MVP Priority)

## Goal
Deploy a public MVP of the Israel Flights Dashboard with real, accurate flight data, working filters, and a production-ready cloud environment.

---

## Critical for MVP

### 1. Filter Functionality Issues
**Status:** Critical  
**Description:** Filters by airline, day, and date are not working properly.  
**Current State:**  
- Frontend filters exist but may not be properly connected to backend  
- Date range filtering logic needs review  
- Day of week filtering not implemented in backend  
- Airline filtering works but may have data issues  
**Files Affected:**  
- `frontend/src/components/DashboardFilters.tsx`  
- `frontend/src/pages/Index.tsx`  
- `backend/app/api/flights.py`  
- `backend/app/api/airline_endpoints.py`  
**Action Required:**  
- Debug filter parameter passing from frontend to backend  
- Implement day of week filtering in backend  
- Fix date range filtering logic  
- Test all filter combinations  

---

### 2. Airline Statistics Filtering
**Status:** Critical  
**Description:** Worst and best airlines tables need to display only airlines with at least 20 flights.  
**Current State:**  
- `min_flights` parameter exists in API but defaults to 1  
- Frontend doesn't enforce minimum flight requirement  
- Backend service supports filtering but not enforced  
**Files Affected:**  
- `backend/app/api/airline_endpoints.py`  
- `backend/app/services/airline_aggregation.py`  
- `frontend/src/pages/Index.tsx`  
**Action Required:**  
- Update API default `min_flights` from 1 to 20  
- Update frontend to pass `min_flights=20` parameter  
- Test that only airlines with 20+ flights appear in tables  

---

### 3. Flight Data Pipeline Issues
**Status:** Critical  
**Description:** Need to download all flights from S3 and insert them into the database.  
**Current State:**  
- Airflow pipeline exists but may not be running regularly  
- Data exists in S3 but may not be fully synced to PostgreSQL  
- Manual download script available but not automated  
**Files Affected:**  
- `airflow/dags/flight_pipeline.py`  
- `airflow/etl/download_and_load.py`  
- `airflow/utils/db_utils.py`  
**Action Required:**  
- Verify Airflow DAG is running and scheduled properly  
- Check if all S3 data has been processed and loaded to DB  
- Run manual download script if needed  
- Monitor data freshness and completeness  

---

### 4. Cloud Deployment
**Status:** Critical  
**Description:** Deploy the project to cloud infrastructure with a proper domain instead of running locally.  
**Current State:**  
- Project runs locally on localhost:8000 (backend) and localhost:3000 (frontend)  
- No cloud infrastructure setup  
- No domain configuration  
**Files Affected:**  
- `docker-compose.yaml` files (airflow and backend)  
- `Dockerfile` files  
- `frontend/package.json`  
- `backend/app/main.py`  
- Environment configuration files  
**Action Required:**  
- Choose cloud provider (AWS, GCP, Azure, DigitalOcean, etc.)  
- Set up container orchestration (Docker Swarm, Kubernetes, or managed services)  
- Configure domain and SSL certificates  
- Set up CI/CD pipeline for deployments  
- Configure production environment variables  
- Set up monitoring and logging  
- Configure production database  
- Update API endpoints to use production domain  

---

### 5. Language and Theme Configuration
**Status:** Medium  
**Description:** Set default language to Hebrew and default theme to light mode.  
**Current State:**  
- Language context exists but may default to English  
- Theme system may not be properly configured  
**Files Affected:**  
- `frontend/src/contexts/LanguageContext.tsx`  
- `frontend/src/App.tsx`  
- `frontend/src/index.css`  
- `frontend/src/components/`  
**Action Required:**  
- Set Hebrew as default language in LanguageContext  
- Configure light theme as default  
- Ensure RTL layout works properly  
- Test all components with Hebrew text and light theme  
- Replace hardcoded English text with translation keys  

---

## Post-MVP (To be done after deployment)

### 6. Duplicate API Endpoints
**Status:** Medium  
**Description:** Duplicate `/destinations` endpoints in flights.py  
**Files Affected:**  
- `backend/app/api/flights.py`  
**Action Required:**  
- Remove duplicate endpoint definition  

---

### 7. Missing Error Handling
**Status:** Medium  
**Description:** Some API endpoints lack proper error handling.  
**Files Affected:**  
- `backend/app/api/airline_endpoints.py`  
- `frontend/src/hooks/useApiData.ts`  
**Action Required:**  
- Add comprehensive error handling and user feedback  

---

### 8. Data Quality Issues
**Status:** Medium  
**Description:** Potential data quality issues in flight data.  
**Files Affected:**  
- `airflow/etl/transform.py`  
- `airflow/utils/db_utils.py`  
**Action Required:**  
- Review data validation logic  
- Add data quality checks  
- Handle missing or invalid data gracefully  

---

### 9. Performance Optimization
**Status:** Medium  
**Description:** Optimize database queries and API responses.  
**Action Required:**  
- Add indexes for frequently queried fields  
- Implement query result caching  
- Optimize pagination for large datasets  

---

### 10. Frontend State Management
**Status:** Medium  
**Description:** Improve filter state management and data flow.  
**Files Affected:**  
- `frontend/src/pages/Index.tsx`  
- `frontend/src/hooks/useApiData.ts`  
**Action Required:**  
- Implement proper state management (Context API or Redux)  
- Add loading states for async operations  
- Improve error handling  

---

### 11. API Documentation
**Status:** Low  
**Description:** Add comprehensive API documentation.  
**Action Required:**  
- Document all API endpoints  
- Add OpenAPI/Swagger documentation  
- Create API usage guide  

---

### 12. Testing
**Status:** Low  
**Description:** Add comprehensive testing suite.  
**Action Required:**  
- Add unit tests for backend  
- Add integration tests for API  
- Add frontend component and E2E tests  

---

### 13. Airflow Monitoring
**Status:** Medium  
**Description:** Set up monitoring and alerting for Airflow.  
**Action Required:**  
- Configure monitoring  
- Add alerts for failed DAGs  
- Monitor performance  

---

### 14. Data Validation
**Status:** Medium  
**Description:** Implement comprehensive data validation.  
**Action Required:**  
- Add validation checks to ETL pipeline  
- Implement validation rules  
- Add reporting for data quality  

---

## Summary of Updated Priorities

1. Fix filter functionality  
2. Apply min_flights ≥ 20  
3. Sync all S3 data to database  
4. Deploy to cloud with domain  
5. Configure Hebrew and Light Theme  
6. Remove duplicate endpoints  
7. Add error handling  
8. Add data validation  
9. Optimize performance  
10. Improve state management  
11. Add testing suite  
12. Add API documentation  
13. Set up Airflow monitoring  
