import pandas as pd
import logging
import os
import glob
import tempfile
from typing import List
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
import json
from config.settings import S3_BUCKET_NAME

def cleanup_temp_files(file_paths: List[str]) -> None:
    """
    Deletes a list of temporary files from local disk.

    Args:
        file_paths (list[str]): List of full file paths to delete.

    Returns:
        None
    """
    import os
    import logging

    for path in file_paths:
        try:
            os.remove(path)
            logging.info(f"Deleted temp file: {path}")
        except FileNotFoundError:
            logging.warning(f"Temp file not found (already deleted?): {path}")
        except Exception as e:
            logging.error(f"Error deleting temp file '{path}': {str(e)}")

def save_local_inspection_copy(df: pd.DataFrame, filename: str) -> None:
    """
    Deletes old local processed files and saves the new DataFrame locally
    under the given filename.

    Args:
        df (pd.DataFrame): DataFrame to be saved.
        filename (str): Filename to use (e.g., 'flights_data_20250822_120000.csv').

    Returns:
        None
    """
    import os
    import glob

    local_folder: str = "/opt/airflow/data/files"
    local_output_path: str = os.path.join(local_folder, filename)

    # Delete previous inspection files
    for old_file in glob.glob(os.path.join(local_folder, "flights_data_*.csv")):
        os.remove(old_file)

    # Ensure directory exists
    os.makedirs(local_folder, exist_ok=True)

    # Save the new inspection copy
    df.to_csv(local_output_path, index=False)

def save_csv_temp(df: pd.DataFrame) -> str:
    """
    Saves a DataFrame to a temporary CSV file.

    Args:
        df (pd.DataFrame): DataFrame to be saved.

    Returns:
        str: Path to the temporary CSV file.
    """
    import tempfile

    temp_file_path: str
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv', delete=False) as temp_file:
        df.to_csv(temp_file.name, index=False)
        temp_file_path = temp_file.name

    return temp_file_path

def upload_file_to_s3(local_path: str, s3_key: str) -> str:
    """
    Uploads a local file to S3 and returns the full S3 path.

    Args:
        local_path (str): Path to the local file to upload.
        s3_key (str): Target key to use in the S3 bucket.

    Returns:
        str: Full S3 path where the file was uploaded.
    """
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    bucket_name: str = S3_BUCKET_NAME
    s3_hook: S3Hook = S3Hook(aws_conn_id='aws_s3')

    s3_hook.load_file(
        filename=local_path,
        key=s3_key,
        bucket_name=bucket_name,
        replace=True
    )

    s3_path: str = f"s3://{bucket_name}/{s3_key}"
    return s3_path

def download_json_from_s3(s3_path: str) -> str:
    """
    Downloads a JSON file from S3 to a local temporary file.

    Args:
        s3_path (str): Full S3 path in the format 's3://bucket/key.json'

    Returns:
        str: Local path to the downloaded temporary JSON file
    """
    import tempfile
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    s3_hook: S3Hook = S3Hook(aws_conn_id='aws_s3')
    bucket_name: str
    key: str

    # Parse S3 path
    s3_clean: str = s3_path.replace("s3://", "")
    bucket_name, key = s3_clean.split("/", 1)

    # Create a temporary file for the download
    with tempfile.NamedTemporaryFile(mode='w+b', suffix='.json', delete=False) as temp_file:
        s3_obj = s3_hook.get_key(bucket_name=bucket_name, key=key)
        s3_obj.download_fileobj(temp_file)
        temp_path: str = temp_file.name

    return temp_path

def transform_flight_data(json_path: str) -> pd.DataFrame:
    """
    Transforms flight data with better column names and calculated fields.
    """
    import pandas as pd

    # Load JSON data into DataFrame
    with open(json_path, 'r') as f:
        data = json.load(f)
    df = pd.DataFrame(data)

    # Rename columns to be more descriptive
    column_mapping = {
        'CHOPER': 'airline_code',
        'CHFLTN': 'flight_number', 
        'CHOPERD': 'airline_name',
        'CHSTOL': 'scheduled_departure_time',  # This maps to the new name
        'CHPTOL': 'actual_departure_time',
        'CHAORD': 'arrival_departure_code',
        'CHLOC1': 'airport_code',
        'CHLOC1D': 'airport_name_english',
        'CHLOC1TH': 'airport_name_hebrew',
        'CHLOC1T': 'city_name_english',
        'CHLOC1CH': 'country_name_hebrew',
        'CHLOCCT': 'country_name_english',
        'CHTERM': 'terminal_number',
        'CHCINT': 'check_in_time',
        'CHCKZN': 'check_in_zone',
        'CHRMINE': 'status_english',
        'CHRMINH': 'status_hebrew'
    }
    
    df = df.rename(columns=column_mapping)
    
    # Convert time columns to datetime
    df["scheduled_departure"] = pd.to_datetime(df["scheduled_departure_time"], errors="coerce")
    df["actual_departure"] = pd.to_datetime(df["actual_departure_time"], errors="coerce")
    
    # Calculate delay in minutes
    df["delay_minutes"] = (
        (df["actual_departure"] - df["scheduled_departure"])
        .dt.total_seconds() / 60.0
    )
    
    return df

def check_data_completeness(df: pd.DataFrame) -> str:
    """
    Check data completeness with status-aware validation.
    Only validate check-in fields for departed flights.
    """
    try:
        # Critical fields that should always be present
        critical_fields = [
            'airline_code', 'flight_number', 'airline_name',
            'scheduled_departure_time', 'actual_departure_time',
            'airport_code', 'status_english'
        ]
        
        # Check critical fields for all records
        missing_values = {}
        for column in critical_fields:
            if column in df.columns:
                missing_count = df[column].isnull().sum()
                if missing_count > 0:
                    missing_values[column] = missing_count
        
        # Check check-in fields only for departed flights
        departed_flights = df[df['status_english'] == 'DEPARTED']
        if len(departed_flights) > 0:
            checkin_fields = ['check_in_time', 'check_in_zone']
            for column in checkin_fields:
                if column in df.columns:
                    missing_count = departed_flights[column].isnull().sum()
                    if missing_count > 0:
                        missing_values[f"{column}_departed_only"] = missing_count
        
        if missing_values:
            error_details = ", ".join([f"{col}: {count} missing" for col, count in missing_values.items()])
            raise ValueError(f"Data completeness check failed. Missing values found: {error_details}")
        
        logging.info("Data completeness check passed - no missing values found in critical fields")
        return "Data completeness check passed successfully"
        
    except Exception as e:
        logging.error(f"Error in check_data_completeness: {str(e)}")
        raise

def transform_flight_data_pipeline(s3_path: str, timestamp: str) -> str:
    """
    Complete transformation pipeline for flight data:
    - Download from S3
    - Apply transformation (add delay_minutes)
    - Check data completeness
    - Save to CSV
    - Upload processed CSV to S3
    - Save one local inspection copy
    - Clean up temp files
    
    Args:
        s3_path: S3 path to raw JSON data
        timestamp: Timestamp string for file naming
        
    Returns:
        str: S3 path to processed CSV file
    """
    try:
        # Step 1: Download JSON from S3 to a temp file
        json_path = download_json_from_s3(s3_path)
        logging.info(f"[json_path] {json_path}")

        # Step 2: Transform the data by adding 'delay_minutes' column
        df = transform_flight_data(json_path)
        logging.info(f"[df.shape] {df.shape}")

        # Step 3: Check data completeness before saving to CSV
        check_data_completeness(df)
        logging.info("Data completeness validation skipped")

        # Step 4: Save transformed DataFrame to a temporary CSV file
        csv_path = save_csv_temp(df)
        logging.info(f"[csv_path] {csv_path}")

        # Step 5: Upload the processed CSV to S3
        processed_key = f"processed/flights_data_{timestamp}.csv"
        s3_result = upload_file_to_s3(csv_path, processed_key)
        logging.info(f"[s3_result] {s3_result}")

        # Step 6: Save one local inspection copy (and delete older ones)
        inspection_file = os.path.basename(processed_key)
        save_local_inspection_copy(df, inspection_file)
        logging.info(f"[local_inspection_file] {inspection_file}")

        # Step 7: Clean up temporary files
        temp_files = [json_path, csv_path]
        cleanup_temp_files(temp_files)
        logging.info(f"Cleaned up temp files: {temp_files}")

        return s3_result

    except Exception as e:
        logging.error(f"Error in transform_flight_data_pipeline: {str(e)}")
        raise
