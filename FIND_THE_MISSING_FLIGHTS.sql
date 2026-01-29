-- ============================================
-- STEP-BY-STEP GUIDE TO FIND WHY API SHOWS 35,114 INSTEAD OF 84,594
-- ============================================

-- STEP 1: Verify total flights in database
-- Expected result: 84,594
SELECT COUNT(*) as total_flights_in_database 
FROM flights;

-- STEP 2: Check if API is filtering by date
-- Run each query and see which one gives you 35,114

-- 2a. Last 30 days
SELECT COUNT(*) as count_last_30_days
FROM flights 
WHERE scheduled_time >= CURRENT_DATE - INTERVAL '30 days';

-- 2b. Last 90 days  
SELECT COUNT(*) as count_last_90_days
FROM flights 
WHERE scheduled_time >= CURRENT_DATE - INTERVAL '90 days';

-- 2c. Last year
SELECT COUNT(*) as count_last_year
FROM flights 
WHERE scheduled_time >= CURRENT_DATE - INTERVAL '1 year';

-- 2d. 2024 only
SELECT COUNT(*) as count_2024
FROM flights 
WHERE scheduled_time >= '2024-01-01' AND scheduled_time < '2025-01-01';

-- 2e. 2025 only
SELECT COUNT(*) as count_2025
FROM flights 
WHERE scheduled_time >= '2025-01-01';

-- STEP 3: Check if API is filtering by airline_code/airline_name
-- (We already know this gives 84,594, so this is NOT the issue)
SELECT COUNT(*) as flights_with_airline_info
FROM flights 
WHERE airline_code IS NOT NULL AND airline_name IS NOT NULL;

-- STEP 4: Check if there's a limit on airlines affecting the count
-- This checks if only flights from airlines with >= 1 flight are counted
-- (min_flights default is 1, so this shouldn't filter anything)
SELECT COUNT(*) as flights_from_airlines_with_at_least_1_flight
FROM flights
WHERE airline_code IN (
    SELECT airline_code 
    FROM flights 
    GROUP BY airline_code, airline_name
    HAVING COUNT(*) >= 1
);

-- STEP 5: Check date range of your data
-- This helps understand what date range might be filtered
SELECT 
    MIN(scheduled_time) as earliest_flight,
    MAX(scheduled_time) as latest_flight,
    COUNT(*) as total_count
FROM flights;

-- STEP 6: Count flights by month to see distribution
-- Look for a month or date range that has around 35,114 flights
SELECT 
    DATE_TRUNC('month', scheduled_time) as month,
    COUNT(*) as flights_per_month
FROM flights
GROUP BY DATE_TRUNC('month', scheduled_time)
ORDER BY month DESC
LIMIT 12;

-- ============================================
-- WHAT TO DO:
-- ============================================
-- 1. Run STEP 1 - confirm you get 84,594
-- 2. Run STEP 2 queries (2a through 2e) - see if any give 35,114
-- 3. If one of them gives 35,114, that's your answer! The API is filtering by that date range
-- 4. Also check your backend console logs when you load the dashboard
-- 5. Check browser Network tab → find /api/v1/airlines/stats request → check URL parameters
