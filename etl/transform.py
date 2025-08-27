import pandas as pd
import logging
import os
import glob
import tempfile
from typing import List
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

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

    bucket_name: str = "bbucket2"
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
    Transforms flight data from a JSON file by adding a 'delay_minutes' column.

    Args:
        json_path (str): Path to the local JSON file containing flight data.

    Returns:
        pd.DataFrame: Transformed DataFrame with a new 'delay_minutes' column.
    """
    import pandas as pd

    df: pd.DataFrame = pd.read_json(json_path)
    df["scheduled_departure"] = pd.to_datetime(df["CHSTOL"], errors="coerce")
    df["actual_departure"] = pd.to_datetime(df["CHPTOL"], errors="coerce")
    df["delay_minutes"] = (
        (df["actual_departure"] - df["scheduled_departure"])
        .dt.total_seconds() / 60.0
    )

    return df
