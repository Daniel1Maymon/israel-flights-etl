# Process gz files from S3 bucket

## Overview

Create a standalone script that processes gzipped JSON files from S3 and runs them through the complete ETL pipeline by calling the core logic from DAG functions directly (no XCom simulation).

## Implementation Plan

### 1. Create script: `airflow/scripts/process_gz_files.py`

The script will:

- List all `.gz` files from `etl-flight-pipeline-bucket/raw/flights/`
- For each file:

  1. Download and decompress the gz file
  2. Upload decompressed JSON to `uploads/flights_data_TIMESTAMP.json`
  3. Validate the file (extract core logic from `validate_data`)
  4. Transform the data (extract core logic from `transform_data`)
  5. Load to database (extract core logic from `load_to_db`)

- Include extensive logging at each step

### 2. Key Components

**File Processing:**

- Use `download_gzipped_json_from_s3()` from `etl/download_and_load.py` to download and decompress
- Upload decompressed JSON to S3 using `S3Hook` to `uploads/flights_data_TIMESTAMP.json`
- Use existing utility functions from `etl/transform.py` and `utils/db_utils.py`

**Core Logic Extraction:**

Instead of using DAG functions with XCom, extract and call the core logic directly:

1. **Validate step** (from `validate_data`):

   - Check if file exists in S3 using `S3Hook.check_for_key()`
   - Check file size > 0 using `S3Hook.get_key()`
   - Log: "Validation passed: file exists and is not empty"

2. **Transform step** (from `transform_data`):

   - Use `download_json_from_s3()` from `etl/transform.py`
   - Use `transform_flight_data()` from `etl/transform.py`
   - Use `save_csv_temp()` and `upload_file_to_s3()` from `etl/transform.py`
   - Log: "Transformed X records to CSV with Y columns"
   - Return the CSV S3 path

3. **Load step** (from `load_to_db`):

   - Use `download_csv_from_s3()` from `utils/db_utils.py`
   - Use `compute_flight_uuid()` from `utils/db_utils.py`
   - Use `create_flights_table_if_not_exists()` and `upsert_flight_data()` from `utils/db_utils.py`
   - **Note**: The `upsert_flight_data()` function already correctly handles updates:
     - Uses `ON CONFLICT (flight_id) DO UPDATE SET` to update only updatable fields
     - Updates: actual_time, terminal, checkin_counters, checkin_zone, status_en, status_he, delay_minutes, scrape_timestamp, raw_s3_path
     - Key fields (airline_code, flight_number, direction, location_iata, scheduled_time) are part of flight_id and not updated
   - Log: "Loaded X rows (inserted new or updated existing flights)"

**Logging:**

- Log file discovery (how many files found)
- Log each file being processed with filename
- Log each step: download, decompress, upload, validate, transform, load
- Log record counts at each step
- Log success/failure for each file
- Log summary at the end (total files, successful, failed)

### 3. Script Structure

```python
# Pseudo-code structure:
1. List all .gz files in s3://etl-flight-pipeline-bucket/raw/flights/
2. Log: "Found X files to process"
3. For each file:
   a. Log: "Processing file: {filename}"
   b. Download and decompress gz file → get records list
   c. Log: "Decompressed X records"
   d. Upload JSON to uploads/ folder with timestamp → get S3 path
   e. Log: "Uploaded JSON to {s3_path}"
   f. Validate: check file exists and not empty
   g. Log: "Validation passed"
   h. Transform: download JSON, transform, upload CSV → get CSV S3 path
   i. Log: "Transformed to CSV: {csv_s3_path}, {row_count} rows"
   j. Load: download CSV, compute UUIDs, upsert to DB
   k. Log: "Loaded {rows_loaded} rows to database (inserted new or updated existing)"
   l. Log: "File processed successfully" or "File failed: {error}"
4. Print summary: "Processed X files, Y successful, Z failed"
```

### 4. Files to Create/Modify

- **New file**: `airflow/scripts/process_gz_files.py`
  - Import `download_gzipped_json_from_s3` from `etl/download_and_load.py`
  - Import utility functions from `etl/transform.py` and `utils/db_utils.py`
  - Use `S3Hook` for S3 operations
  - Use `PostgresHook` for database operations (with fallback to direct connection)
  - Extensive logging throughout

### 5. Dependencies

- Uses existing utility functions (no changes to DAG or db_utils needed)
- The upsert logic in `upsert_flight_data()` already correctly updates only updatable fields
- Requires same dependencies as DAG (S3Hook, PostgresHook, etc.)
- Handles gz decompression using existing utility

### 6. Error Handling

- Continue processing next file if one fails
- Log errors for each file with full traceback
- Track failed files in summary
- Don't stop on single file failure

## Implementation Details

The script will:

1. Connect to S3 and list files matching `raw/flights/*.gz`
2. For each file, process through: decompress → upload JSON → validate → transform → load
3. Pass S3 paths directly between steps (no XCom needed)
4. Log extensively at each step with clear messages
5. The database upsert will automatically:

   - Insert new flights if flight_id doesn't exist
   - Update only updatable fields if flight_id already exists (actual_time, terminal, checkin_counters, checkin_zone, status_en, status_he, delay_minutes, scrape_timestamp, raw_s3_path)

6. Provide a final summary of processing results