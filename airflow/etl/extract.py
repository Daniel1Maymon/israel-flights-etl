import requests
import json
import logging
import tempfile
from datetime import datetime
from typing import Tuple
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
import os
from config.settings import S3_BUCKET_NAME, S3_RAW_PATH

def validate_extracted_data(records: list, response: dict) -> None:
    """
    Validate data during extraction phase.
    Raises ValueError if validation fails, otherwise continues.
    
    Args:
        records: List of records extracted from API
        response: Full API response for validation
        
    Raises:
        ValueError: If validation fails
    """
    # 1. Schema Validation - Check if required fields exist
    if records:
        first_record = records[0]
        required_fields = ["CHSTOL", "CHPTOL", "CHOPER", "CHFLTN"]  # Use actual field names
        missing_fields = [field for field in required_fields if field not in first_record]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
    
    # 2. Record Count Validation - Ensure we got substantial data
    if len(records) == 0:
        raise ValueError("No records extracted from API")
    elif len(records) < 100:  # Assuming we expect substantial flight data
        logging.warning(f"Low record count: {len(records)} (expected more)")
    
    # 3. API Response Quality - Validate response structure
    if "result" not in response:
        raise ValueError("Invalid API response structure: missing 'result' key")
    
    # 4. Data Type Validation - Check if critical fields have expected types
    if records:
        sample_record = records[0]
        if "CHSTOL" in sample_record and not isinstance(sample_record["CHSTOL"], str):
            logging.warning("CHSTOL field is not string type as expected")
        if "flight_number" in sample_record and not isinstance(sample_record["flight_number"], (str, int)):
            logging.warning("flight_number field has unexpected type")
    
    # If we get here, validation passed
    logging.info(f"Extraction validation passed: {len(records)} records")

def extract_from_api(resource_id: str, batch_size: int = 1000) -> tuple[list, dict]:
    """
    Extract data from CKAN API using pagination.
    
    Args:
        resource_id: API resource ID to extract
        batch_size: Number of records per batch
        
    Returns:
        tuple: (all_records, api_response)
    """
    base_url = "https://data.gov.il/api/3/action/datastore_search"
    all_records = []
    offset = 0
    api_response = None

    while True:
        params = {"resource_id": resource_id, "limit": batch_size, "offset": offset}
        response = requests.get(base_url, params=params, timeout=300)

        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code}")

        result = response.json()["result"]
        records = result["records"]
        
        # Store first response for validation
        if offset == 0:
            api_response = response.json()
        
        if not records:
            break

        all_records.extend(records)
        offset += batch_size
        logging.info(f"Fetched {len(records)} records (total: {len(all_records)})")

    return all_records, api_response

def upload_to_s3(data: list, s3_key: str, bucket_name: str) -> str:
    """
    Upload data to S3 and return the S3 path.
    
    Args:
        data: Flight records data to upload
        s3_key: S3 key for the file
        bucket_name: S3 bucket name
        
    Returns:
        str: Full S3 path
    """
    # Create temporary file for S3 upload
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
        json.dump(data, tmp_file, ensure_ascii=False, indent=2)
        tmp_file_path = tmp_file.name

    try:
        # Upload to S3
        s3_hook = S3Hook(aws_conn_id='aws_s3')
        s3_hook.load_file(
            filename=tmp_file_path,
            key=s3_key,
            bucket_name=bucket_name,
            replace=True
        )

        # Return the S3 path
        s3_path = f"s3://{bucket_name}/{s3_key}"
        return s3_path

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

def fetch_flight_data(bucket_name: str = S3_BUCKET_NAME) -> str:
    """
    Fetch raw flight data from CKAN API and upload to S3.
    
    Args:
        bucket_name: S3 bucket name to upload to
        
    Returns:
        str: S3 path where the file was uploaded
        
    Raises:
        ValueError: If data validation fails
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_key = f"{S3_RAW_PATH}/flights_data_{timestamp}.json"
    resource_id = "e83f763b-b7d7-479e-b172-ae981ddc6de5"

    try:
        # Extract data from API
        all_records, api_response = extract_from_api(resource_id)
        
        # Validate extracted data
        logging.info("Starting extraction validation...")
        validate_extracted_data(all_records, api_response)
        
        # If we get here, validation passed - continue with pipeline
        logging.info(f"Extraction validation PASSED: {len(all_records)} records")
        
        # Upload clean data to S3 (no validation metadata needed)
        s3_path = upload_to_s3(all_records, s3_key, bucket_name)
        
        logging.info(f"Successfully extracted and validated {len(all_records)} records and uploaded to S3: {s3_path}")
        return s3_path

    except Exception as e:
        logging.error(f"Error in fetch_flight_data: {str(e)}")
        raise
