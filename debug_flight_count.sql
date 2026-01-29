-- Debug queries to find why API returns 35,114 instead of 84,594

-- 1. Total flights in database
SELECT COUNT(*) as total_flights FROM flights;
-- Expected: 84,594

-- 2. Flights with airline_code AND airline_name (not NULL)
SELECT COUNT(*) as flights_with_airline_info 
FROM flights 
WHERE airline_code IS NOT NULL AND airline_name IS NOT NULL;
-- This might match 35,114

-- 3. Flights WITHOUT airline_code OR airline_name (NULL)
SELECT COUNT(*) as flights_without_airline_info 
FROM flights 
WHERE airline_code IS NULL OR airline_name IS NULL;
-- This should be: 84,594 - 35,114 = 49,480

-- 4. Check if they add up
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE airline_code IS NOT NULL AND airline_name IS NOT NULL) as with_airline_info,
    COUNT(*) FILTER (WHERE airline_code IS NULL OR airline_name IS NULL) as without_airline_info,
    COUNT(*) FILTER (WHERE airline_code IS NOT NULL AND airline_name IS NOT NULL) + 
    COUNT(*) FILTER (WHERE airline_code IS NULL OR airline_name IS NULL) as sum
FROM flights;

-- 5. Check date range of flights with airline info vs without
SELECT 
    'With Airline Info' as category,
    MIN(scheduled_time) as earliest_flight,
    MAX(scheduled_time) as latest_flight,
    COUNT(*) as count
FROM flights 
WHERE airline_code IS NOT NULL AND airline_name IS NOT NULL
UNION ALL
SELECT 
    'Without Airline Info' as category,
    MIN(scheduled_time) as earliest_flight,
    MAX(scheduled_time) as latest_flight,
    COUNT(*) as count
FROM flights 
WHERE airline_code IS NULL OR airline_name IS NULL;

-- 6. Check date distribution to find what date range gives 35,114
-- Try different date ranges to match the API count
SELECT 
    'All flights' as filter,
    COUNT(*) as count
FROM flights
UNION ALL
SELECT 
    'Last 30 days' as filter,
    COUNT(*) as count
FROM flights 
WHERE scheduled_time >= CURRENT_DATE - INTERVAL '30 days'
UNION ALL
SELECT 
    'Last 90 days' as filter,
    COUNT(*) as count
FROM flights 
WHERE scheduled_time >= CURRENT_DATE - INTERVAL '90 days'
UNION ALL
SELECT 
    'Last year' as filter,
    COUNT(*) as count
FROM flights 
WHERE scheduled_time >= CURRENT_DATE - INTERVAL '1 year'
UNION ALL
SELECT 
    '2024 only' as filter,
    COUNT(*) as count
FROM flights 
WHERE scheduled_time >= '2024-01-01' AND scheduled_time < '2025-01-01'
UNION ALL
SELECT 
    '2025 only' as filter,
    COUNT(*) as count
FROM flights 
WHERE scheduled_time >= '2025-01-01';

-- 7. Find the exact date range that gives 35,114
-- This will help identify what filter is being applied
SELECT 
    MIN(scheduled_time) as earliest,
    MAX(scheduled_time) as latest,
    COUNT(*) as total_count
FROM flights
ORDER BY scheduled_time DESC
LIMIT 35114;  -- This won't work directly, but helps understand the data

-- 8. Check if there's a date filter by counting flights by year/month
SELECT 
    DATE_TRUNC('month', scheduled_time) as month,
    COUNT(*) as flights_per_month
FROM flights
GROUP BY DATE_TRUNC('month', scheduled_time)
ORDER BY month DESC;
