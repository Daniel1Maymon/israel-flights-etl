-- Restrict the AI-search read-only role to public columns only.
--
-- Context: asking the AI "give me all the information" produced SELECT * FROM flights,
-- which returned every column including raw_s3_path and scrape_timestamp. That is now
-- blocked in two places in application code (sql_guard rejects the projection,
-- ai_search strips internal columns on the way out). This file adds the third layer,
-- and it is the only one that holds if the application code is wrong.
--
-- Postgres enforces column-level SELECT privileges directly: with these grants,
-- `SELECT raw_s3_path FROM flights` fails with "permission denied for column" no matter
-- what SQL reaches the database. Application-layer checks depend on sqlglot modelling
-- every syntax correctly; this one does not depend on parsing at all.
--
-- Run once, as a superuser or the flights table owner:
--   psql "$DATABASE_URL" -f backend/scripts/restrict_ro_role_columns.sql
--
-- Verify afterwards (should raise "permission denied for column raw_s3_path"):
--   psql "$DATABASE_URL_RO" -c 'SELECT raw_s3_path FROM flights LIMIT 1;'
--
-- Note: `SELECT *` by rankair_ro will also fail after this, because * expands to every
-- column including the revoked ones. That is intended -- it is the behaviour that
-- produced the leak.

BEGIN;

-- Drop the table-wide grant; column grants below replace it.
REVOKE SELECT ON flights FROM rankair_ro;

-- Exactly the columns the AI system prompt advertises, and no others.
-- Keep this list in sync with AI_SELECTABLE_COLUMNS in app/services/sql_guard.py.
GRANT SELECT (
    airline_name,
    airline_code,
    direction,
    location_en,
    location_he,
    location_city_en,
    country_en,
    scheduled_time,
    actual_time,
    delay_minutes,
    status_en,
    terminal
) ON flights TO rankair_ro;

COMMIT;

-- Deliberately NOT granted (internal):
--   raw_s3_path        S3 bucket and key layout
--   scrape_timestamp   ETL internals
--   checkin_counters   unused by any client
--   checkin_zone       unused by any client
--   flight_id          surrogate identifier
--   flight_number      not needed for the aggregate answers the feature gives
--   location_iata      not needed
--   country_he         not needed
--   status_he          not needed
