#!/usr/bin/env python3
# Script to process gzipped raw flight files from S3 through the ETL pipeline.
# Steps:
# 1) List gzipped raw files in S3.
# 2) Download and decompress each file.
# 3) Upload JSON back to S3 and validate.
# 4) Transform JSON to CSV and upload processed output.
# 5) Load into Postgres and log progress.
"""
Process gzipped JSON files from S3 bucket and run them through the ETL pipeline.

This script:
- Lists all .gz files from etl-flight-pipeline-bucket/raw/flights/
- For each file: downloads, decompresses, uploads JSON, validates, transforms, and loads to database
- Uses existing functions from the DAG without XCom simulation
- Provides extensive logging at each step
"""

import sys
import os
import json
import logging
import tempfile
from datetime import datetime
import pandas as pd
import psycopg2
import boto3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import S3_BUCKET_NAME, S3_RAW_PATH
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from etl.download_and_load import download_gzipped_json_from_s3
from etl.transform import (
    download_json_from_s3,
    transform_flight_data,
    save_csv_temp,
    upload_file_to_s3,
    cleanup_temp_files
)
from utils.db_utils import (
    download_csv_from_s3,
    compute_flight_uuid,
    create_flights_table_if_not_exists,
    upsert_flight_data
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def upload_json_to_s3(records: list, s3_key: str, bucket_name: str) -> str:
    """
    Upload JSON records to S3.
    
    Args:
        records: List of flight records
        s3_key: S3 key for the file
        bucket_name: S3 bucket name
        
    Returns:
        str: Full S3 path
    """
    # Step 1: Create temporary file with JSON data
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
        json.dump(records, tmp_file, ensure_ascii=False, indent=2)
        tmp_file_path = tmp_file.name
    
    try:
        # Step 2: Upload to S3
        s3_hook = S3Hook(aws_conn_id='aws_s3')
        s3_hook.load_file(
            filename=tmp_file_path,
            key=s3_key,
            bucket_name=bucket_name,
            replace=True
        )
        
        # Step 3: Return S3 path
        s3_path = f"s3://{bucket_name}/{s3_key}"
        return s3_path
    
    finally:
        # Step 4: Clean up temporary file
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


def validate_s3_file(s3_path: str) -> None:
    """
    Validate that the S3 file exists and is not empty.
    
    Args:
        s3_path: Full S3 path to validate
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is empty
    """
    # Step 1: Parse S3 path
    path_parts = s3_path.replace("s3://", "").split("/", 1)
    bucket_name = path_parts[0]
    s3_key = path_parts[1]
    
    # Step 2: Initialize S3 hook
    s3_hook = S3Hook(aws_conn_id='aws_s3')
    
    # Step 3: Check if file exists
    if not s3_hook.check_for_key(bucket_name=bucket_name, key=s3_key):
        raise FileNotFoundError(f"File not found in S3: {s3_path}")
    
    logger.info(f"✓ File exists in S3: {s3_path}")
    
    # Step 4: Check file size > 0
    obj = s3_hook.get_key(bucket_name=bucket_name, key=s3_key)
    if obj.content_length == 0:
        raise ValueError(f"File is empty in S3: {s3_path}")
    
    logger.info(f"✓ File is not empty: {obj.content_length} bytes")


def transform_data_step(s3_path: str) -> str:
    """
    Transform JSON data to CSV and upload to S3.
    
    Args:
        s3_path: S3 path to JSON file
        
    Returns:
        str: S3 path to processed CSV file
    """
    # Step 1: Generate timestamp and processed key
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    processed_key = f"processed/flights_data_{timestamp}.csv"
    logger.info(f"Processing timestamp: {timestamp}")
    logger.info(f"Processed key: {processed_key}")
    
    # Step 2: Download JSON from S3 to a temp file
    json_path = download_json_from_s3(s3_path)
    logger.info(f"✓ Downloaded JSON to temporary file: {json_path}")
    
    # Step 3: Transform the data by adding 'delay_minutes' column
    df = transform_flight_data(json_path)
    logger.info(f"✓ Transformed data: {df.shape[0]} rows, {df.shape[1]} columns")
    
    # Step 4: Save transformed DataFrame to a temporary CSV file
    csv_path = save_csv_temp(df)
    logger.info(f"✓ Saved CSV to temporary file: {csv_path}")
    
    # Step 5: Upload the processed CSV to S3
    s3_result = upload_file_to_s3(csv_path, processed_key)
    logger.info(f"✓ Uploaded CSV to S3: {s3_result}")
    
    # Step 6: Clean up temporary files
    temp_files = [json_path, csv_path]
    cleanup_temp_files(temp_files)
    logger.info(f"✓ Cleaned up temporary files")
    
    return s3_result


def load_to_db_step(s3_path: str) -> int:
    """
    Load CSV data into PostgreSQL database.
    
    Args:
        s3_path: S3 path to CSV file
        
    Returns:
        int: Number of rows loaded
    """
    # Step 1: Download CSV from S3
    csv_path = download_csv_from_s3(s3_path)
    logger.info(f"✓ Downloaded CSV to: {csv_path}")
    
    # Step 2: Load CSV into DataFrame
    df = pd.read_csv(csv_path)
    logger.info(f"✓ Loaded DataFrame: {df.shape[0]} rows, {df.shape[1]} columns")
    
    # Step 3: Compute UUIDs for each flight
    df['flight_id'] = df.apply(compute_flight_uuid, axis=1)
    logger.info(f"✓ Computed UUIDs for {len(df)} flights")
    logger.info(f"✓ Unique flight_id values: {df['flight_id'].nunique()} / Total rows: {len(df)}")
    
    # Step 4: Create PostgresHook with direct connection (for testing outside Airflow)
    try:
        pg_hook = PostgresHook(postgres_conn_id='postgres_flights')
        # Test if connection works
        pg_hook.get_conn().close()
    except Exception as e:
        # If Airflow connection not available, create direct connection wrapper
        logger.info(f"Airflow connection not available, using direct connection: {e}")
        class DirectPostgresHook:
            def __init__(self):
                self.conn = None
            
            def get_conn(self):
                if self.conn is None or self.conn.closed:
                    self.conn = psycopg2.connect(
                        host='localhost',
                        port=5433,
                        database='flights_db',
                        user='daniel',
                        password='daniel'
                    )
                return self.conn
        
        pg_hook = DirectPostgresHook()
    
    # Step 5: Create the flights table if it doesn't exist
    create_flights_table_if_not_exists(pg_hook)
    logger.info(f"✓ Flights table ready")
    
    # Step 6: Upsert data into PostgreSQL
    rows_loaded = upsert_flight_data(df, pg_hook)
    logger.info(f"✓ Successfully loaded {rows_loaded} rows into PostgreSQL (inserted new or updated existing)")
    
    # Step 7: Clean up temporary file
    os.remove(csv_path)
    logger.info(f"✓ Cleaned up temporary CSV file")
    
    return rows_loaded


def process_single_file(bucket_name: str, s3_key: str) -> dict:
    """
    Process a single gz file through the complete ETL pipeline.
    
    This function orchestrates the full ETL process for one file:
    1. Downloads and decompresses the gz file from S3
    2. Uploads the decompressed JSON to the uploads/ folder
    3. Validates the file exists and is not empty
    4. Transforms the JSON data to CSV (adds delay_minutes, renames columns)
    5. Loads the CSV data into PostgreSQL (with upsert logic for existing flights)
    
    Args:
        bucket_name: S3 bucket name (e.g., "etl-flight-pipeline-bucket")
        s3_key: S3 object key (path within bucket), e.g., "raw/flights/file1.gz"
        
    Returns:
        dict: Processing result with:
            - 'status': 'success' or 'failed'
            - 'filename': name of the file processed
            - 'records': number of records (if successful)
            - 'rows_loaded': number of rows loaded to DB (if successful)
            - 'error': error message (if failed)
    """
    # Extract just the filename from the full S3 key path
    # e.g., "raw/flights/file1.gz" -> "file1.gz"
    filename = os.path.basename(s3_key)
    logger.info("=" * 80)
    logger.info(f"Processing file: {filename}")
    logger.info(f"S3 path: s3://{bucket_name}/{s3_key}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Download and decompress gz file
        # This downloads the compressed file from S3, decompresses it, and parses the JSON
        # Returns a list of flight record dictionaries
        logger.info("Step 1: Downloading and decompressing gz file...")
        records = download_gzipped_json_from_s3(bucket_name, s3_key)
        logger.info(f"✓ Decompressed {len(records)} records from gz file")
        
        # Step 2: Upload decompressed JSON to uploads/ folder
        # We upload the decompressed JSON to the uploads/ folder with a timestamp
        # This matches the format expected by the rest of the pipeline
        # The timestamp ensures each file has a unique name
        logger.info("Step 2: Uploading JSON to S3...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_s3_key = f"{S3_RAW_PATH}/flights_data_{timestamp}.json"
        json_s3_path = upload_json_to_s3(records, json_s3_key, bucket_name)
        logger.info(f"✓ Uploaded JSON to: {json_s3_path}")
        
        # Step 3: Validate the file
        # Check that the file exists in S3 and is not empty
        # This is a basic sanity check before processing
        logger.info("Step 3: Validating file...")
        validate_s3_file(json_s3_path)
        logger.info(f"✓ Validation passed")
        
        # Step 4: Transform data
        # This step:
        # - Downloads the JSON from S3
        # - Transforms it (renames columns, adds delay_minutes calculation)
        # - Converts to CSV format
        # - Uploads CSV to processed/ folder in S3
        # Returns the S3 path to the processed CSV file
        logger.info("Step 4: Transforming data...")
        csv_s3_path = transform_data_step(json_s3_path)
        logger.info(f"✓ Transformation complete: {csv_s3_path}")
        
        # Step 5: Load to database
        # This step:
        # - Downloads the CSV from S3
        # - Computes flight_id (UUID) for each flight record
        # - Upserts data into PostgreSQL (inserts new flights or updates existing ones)
        # - Only updates updatable fields if flight already exists (actual_time, terminal, status, etc.)
        logger.info("Step 5: Loading to database...")
        rows_loaded = load_to_db_step(csv_s3_path)
        logger.info(f"✓ Database load complete: {rows_loaded} rows")
        
        logger.info("=" * 80)
        logger.info(f"✓ File processed successfully: {filename}")
        logger.info("=" * 80)
        
        return {
            'status': 'success',
            'filename': filename,
            'records': len(records),
            'rows_loaded': rows_loaded,
            'json_s3_path': json_s3_path,
            'csv_s3_path': csv_s3_path
        }
    
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"✗ File processing failed: {filename}")
        logger.error(f"Error: {str(e)}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            'status': 'failed',
            'filename': filename,
            'error': str(e)
        }


def main():
    """
    Main function to process all gz files from S3.
    
    This function:
    1. Connects to S3 and lists all .gz files in the raw/flights/ folder
    2. Processes each file through the complete ETL pipeline
    3. Collects results from each file processing
    4. Prints a summary of all processing results
    
    The script continues processing even if individual files fail,
    so you get a complete picture of what succeeded and what failed.
    """
    logger.info("=" * 80)
    logger.info("GZ FILES PROCESSING SCRIPT")
    logger.info("=" * 80)
    
    # Step 1: Set up S3 client
    # Create a boto3 S3 client using AWS credentials from environment variables
    # This client will be used to list and interact with S3 objects
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    )
    
    # Step 2: List all .gz files in raw/flights/ folder
    # The prefix filters results to only files in the raw/flights/ directory
    # This is more efficient than listing the entire bucket
    prefix = "raw/flights/"
    logger.info(f"Listing files in s3://{S3_BUCKET_NAME}/{prefix}")
    
    # Make the first request to list objects
    # list_objects_v2 returns up to 1000 objects per request
    # The response contains a 'Contents' list with object metadata
    response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET_NAME,
        Prefix=prefix
    )
    
    # Step 3: Filter for .gz files from the first response
    # 'Contents' is a list of dictionaries, each containing:
    #   - 'Key': the S3 object key (path), e.g., "raw/flights/file1.gz"
    #   - 'Size': file size in bytes
    #   - 'LastModified': timestamp when file was uploaded
    #   - 'ETag': file checksum
    # We only want files ending in .gz (compressed JSON files)
    gz_files = []
    if 'Contents' in response:
        # 'Contents' may not exist if the folder is empty
        for obj in response['Contents']:
            # obj['Key'] is the full path within the bucket, e.g., "raw/flights/flights_data_20250101.gz"
            # We check if it ends with .gz to filter for compressed files
            if obj['Key'].endswith('.gz'):
                # Store just the S3 key (path), not the full s3:// URL
                # Example: "raw/flights/flights_data_20250101.gz"
                # We'll combine it with bucket name later when needed: s3://bucket/key
                gz_files.append(obj['Key'])
    
    # Handle pagination if there are more files
    # S3 list_objects_v2 returns max 1000 objects per request
    # If IsTruncated=True, there are more files and we need to fetch them using ContinuationToken
    while response.get('IsTruncated', False):
        logger.info(f"Fetching next page of files (continuation token)...")
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix,
            ContinuationToken=response.get('NextContinuationToken')
        )
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'].endswith('.gz'):
                    gz_files.append(obj['Key'])
    
    logger.info(f"Found {len(gz_files)} .gz files to process")
    logger.info("=" * 80)
    
    if len(gz_files) == 0:
        logger.warning(f"No .gz files found in s3://{S3_BUCKET_NAME}/{prefix}")
        return
    
    # Step 4: Process each file through the complete ETL pipeline
    # We'll iterate through each gz file and process it sequentially:
    # 1. Download and decompress the gz file (from raw/flights/)
    # 2. Upload the decompressed JSON to uploads/ folder (with timestamp)
    # 3. Validate the file exists and is not empty
    # 4. Transform JSON to CSV (add delay_minutes, rename columns, calculate fields)
    # 5. Load CSV data into PostgreSQL database (with upsert logic - updates existing flights)
    #
    # The results list will contain a dictionary for each file with:
    # - 'status': 'success' or 'failed'
    # - 'filename': the name of the file
    # - 'records': number of records (if successful)
    # - 'rows_loaded': number of rows loaded to DB (if successful)
    # - 'error': error message (if failed)
    results = []
    for i, s3_key in enumerate(gz_files, 1):
        # s3_key is the S3 object key (path within bucket), e.g., "raw/flights/file1.gz"
        # We pass both bucket_name and s3_key to process_single_file
        # enumerate(gz_files, 1) gives us (1, file1), (2, file2), etc. for progress tracking
        logger.info(f"\n[{i}/{len(gz_files)}] Processing file...")
        result = process_single_file(S3_BUCKET_NAME, s3_key)
        # result is a dict with status ('success' or 'failed'), filename, and other details
        # We append it to results so we can generate a summary at the end
        results.append(result)
    
    # Step 5: Print summary of all processing results
    # This gives us a complete overview of what was processed, what succeeded, and what failed
    logger.info("\n" + "=" * 80)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 80)
    
    # Separate results into successful and failed for summary statistics
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    
    # Print overall statistics
    logger.info(f"Total files processed: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    
    # If we had successful files, show aggregate statistics
    if successful:
        # Sum up all records from all successful files
        total_records = sum(r.get('records', 0) for r in successful)
        # Sum up all rows that were loaded into the database
        # Note: rows_loaded may be less than records if some flights already existed (upsert)
        total_rows_loaded = sum(r.get('rows_loaded', 0) for r in successful)
        logger.info(f"Total records processed: {total_records}")
        logger.info(f"Total rows loaded to database: {total_rows_loaded}")
    
    # If any files failed, list them with their error messages
    if failed:
        logger.info("\nFailed files:")
        for result in failed:
            logger.info(f"  - {result['filename']}: {result.get('error', 'Unknown error')}")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
