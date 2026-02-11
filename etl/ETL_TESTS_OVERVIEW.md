# ETL Tests Overview

This document maps each ETL pipeline step to its tests, describing the purpose, inputs, and expected outputs.

| Step | Test | Purpose | Input | Expected Output |
| --- | --- | --- | --- | --- |
| Config | `TestConfig.test_defaults` | Ensure defaults are used when env vars are unset | Empty/blank env vars for CKAN + Postgres | Config dict uses documented defaults (CKAN URL/ID, batch size, schedule interval, pg host/port/db/user/password) |
| Config | `TestConfig.test_env_overrides` | Ensure env vars override defaults | Custom env vars for CKAN + Postgres | Config dict reflects provided env var values |
| Fetch | `TestFetch.test_single_page` | Fetch all records from a single page and stop on empty page | Mocked CKAN API returns records then empty list | Returned list equals first page records |
| Fetch | `TestFetch.test_pagination` | Paginate over multiple pages | Mocked CKAN API returns page1, page2, then empty | Returned list equals concatenated pages |
| Fetch | `TestFetch.test_empty_response` | Handle no records | Mocked CKAN API returns empty list | Returned list is `[]` |
| Fetch | `TestFetch.test_api_error` | Raise on non-200 response | Mocked CKAN API response with `status_code=500` | Exception raised with `"API request failed"` |
| Fetch | `TestFetch.test_request_exception` | Propagate network errors | Mocked `requests.get` raises `ConnectionError` | `ConnectionError` is raised |
| Transform | `TestTransform.test_column_renaming` | Ensure all expected English columns are created | Sample CKAN record with Hebrew/legacy fields | DataFrame contains all expected column names |
| Transform | `TestTransform.test_delay_calculation` | Compute delay in minutes | Sample record with scheduled/actual times | `delay_minutes` exists and equals `(actual - scheduled)` in minutes |
| Transform | `TestTransform.test_negative_delay` | Handle early flights | Sample record where actual time is earlier | `delay_minutes` is negative (e.g., `-15.0`) |
| Transform | `TestTransform.test_nat_handling` | Handle missing actual time | Sample record with `CHPTOL = None` | `delay_minutes` is `NaN` (no crash) |
| Transform | `TestTransform.test_empty_input` | Handle empty input | Empty list `[]` | Empty DataFrame |
| Transform | `TestTransform.test_scheduled_actual_datetime_columns` | Ensure datetime columns are created | Sample record with timestamps | `scheduled_departure` and `actual_departure` columns exist with non-null values |
| Load | `TestLoad.test_compute_flight_uuid` | Create deterministic flight UUID | Series with natural key fields | MD5 of `airline_code_flight_number_arrival_departure_code_airport_code_scheduled_departure` |
| Load | `TestLoad.test_uuid_deterministic` | Same input yields same UUID | Identical Series input twice | Both UUIDs are equal |
| Load | `TestLoad.test_uuid_differs_for_different_flights` | Different inputs yield different UUIDs | Two Series with different flight numbers | UUIDs are different |
| Load | `TestLoad.test_create_table_ddl` | Create flights table if missing | Mock DB connection | Executes `CREATE TABLE IF NOT EXISTS flights ...` and commits |
| Load | `TestLoad.test_upsert_sql` | Upsert records into DB | Non-empty DataFrame + mock DB connection | Executes `INSERT ... ON CONFLICT DO UPDATE`, returns rows inserted, commits |
| Load | `TestLoad.test_upsert_empty_df` | No-op on empty DataFrame | Empty DataFrame + mock DB connection | Returns `0` without errors |
| Pipeline | `TestPipeline.test_run_pipeline_orchestration` | Ensure fetch → transform → load order | Mock config + mocked fetch/transform/load | Each function called once in order |
| Pipeline | `TestPipeline.test_run_pipeline_empty_fetch` | Skip transform/load on empty fetch | Mocked fetch returns `[]` | Transform/load not called |
| Pipeline | `TestPipeline.test_run_pipeline_fetch_error` | Propagate fetch errors | Mocked fetch raises `Exception("API down")` | Exception raised with matching message |

Notes:
- Tests are located in `etl/tests/test_etl.py`.
- Fetch tests use mocks for network calls.
- Load tests use mock DB connections and validate SQL execution patterns.
