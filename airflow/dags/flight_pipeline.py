from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import json
import logging
import tempfile
import os
import requests
import pandas as pd
import glob
import hashlib
from etl.transform import (
    download_json_from_s3,
    transform_flight_data,
    save_csv_temp,
    upload_file_to_s3,
    save_local_inspection_copy,
    cleanup_temp_files
)
from utils.db_utils import (
    download_csv_from_s3,
    compute_flight_uuid,
    create_flights_table_if_not_exists,
    upsert_flight_data
)
from config.settings import S3_BUCKET_NAME, S3_RAW_PATH

# Default arguments for all tasks
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Step 1: Fetch raw data from API and upload to S3
def fetch_data(**context):
    """
    Step 1: Fetch raw flight data from CKAN API (data.gov.il).
    - Downloads the full dataset using pagination.
    - Saves file temporarily and uploads to S3.
    - Keeps a single local copy for manual inspection.
    """
    import tempfile
    import glob
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    task_instance = context['task_instance']
    bucket_name = S3_BUCKET_NAME
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_key = f"{S3_RAW_PATH}/flights_data_{timestamp}.json"
    local_folder = "/opt/airflow/data/files"
    local_inspection_path = os.path.join(local_folder, f"flights_data_{timestamp}.json")

    base_url = "https://data.gov.il/api/3/action/datastore_search"
    resource_id = "e83f763b-b7d7-479e-b172-ae981ddc6de5"

    all_records = []
    offset = 0
    batch_size = 1000

    try:
        while True:
            params = {"resource_id": resource_id, "limit": batch_size, "offset": offset}
            response = requests.get(base_url, params=params, timeout=300)

            if response.status_code != 200:
                raise Exception(f"API request failed: {response.status_code}")

            result = response.json()["result"]
            records = result["records"]
            if not records:
                break

            all_records.extend(records)
            offset += batch_size
            logging.info(f"Fetched {len(records)} records (total: {len(all_records)})")

        # Create a temporary file and write the data to it
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
            json.dump(all_records, tmp_file, ensure_ascii=False, indent=2)
            tmp_file_path = tmp_file.name

        # Upload to S3
        s3_hook = S3Hook(aws_conn_id='aws_s3')
        s3_hook.load_file(
            filename=tmp_file_path,
            key=s3_key,
            bucket_name=bucket_name,
            replace=True
        )

        # Delete the temporary file
        os.remove(tmp_file_path)

        # Clean up old local files before saving a new inspection copy
        for old_file in glob.glob(os.path.join(local_folder, "flights_data_*.json")):
            os.remove(old_file)

        # Save a new local copy for inspection
        os.makedirs(local_folder, exist_ok=True)
        with open(local_inspection_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)

        # Push the S3 path to XCom
        s3_path = f"s3://{bucket_name}/{s3_key}"
        task_instance.xcom_push(key='raw_s3_path', value=s3_path)

        logging.info(f"Uploaded to S3: {s3_path}")
        logging.info(f"Saved local inspection copy: {local_inspection_path}")

        return s3_path

    except Exception as e:
        logging.error(f"Error in fetch_data: {str(e)}")
        raise

# Step 2: Validate raw data (basic checks)
def validate_data(**context):
    """
    Step 2: Validate the raw data file.
    - Checks if the file exists in S3.
    - Verifies the file is not empty.
    - (Optional) Ensures schema/columns are correct.
    - Passes the raw S3 path to the next task if valid.
    """
    try:
        # Access the task instance for XCom
        task_instance = context['task_instance']

        s3_path = task_instance.xcom_pull(task_ids="fetch_data", key="raw_s3_path")
        path_parts = s3_path.replace("s3://", "").split("/", 1) # s3://<bucket>/<folder1>/<folder2>/.../<filename>
        bucket_name = path_parts[0]
        s3_key = path_parts[1]

        # Initialize S3 hook (make sure aws_conn_id exists in Airflow Connections)
        s3_hook = S3Hook(aws_conn_id="aws_s3")

        # Check if the object exists in the bucket
        if not s3_hook.check_for_key(bucket_name=bucket_name, key=s3_key):
            raise FileNotFoundError(f"File not found in S3: {s3_path}")

        # Log success
        logging.info(f"Successfully validated data in S3: {s3_path}")

        # Push the S3 path to XCom so next tasks can use it
        task_instance.xcom_push(key='raw_s3_path', value=s3_path)

        # Check file size > 0
        obj = s3_hook.get_key(bucket_name=bucket_name, key=s3_key)
        if obj.content_length == 0:
            raise ValueError(f"File is empty in S3: {s3_path}")

        # Log success
        logging.info(f"Successfully validated data in S3: {s3_path}")

        # Pass the same path forward
        task_instance.xcom_push(key="validated_s3_path", value=s3_path)

        return s3_path

    except Exception as e:
        # Log error if something fails
        logging.error(f"Error in validate_data: {str(e)}")
        raise
    
def transform_data(**context):
    """
    Step 3: Transform the raw flight data:
    - Download from S3
    - Apply transformation (add delay_minutes)
    - Save to CSV
    - Upload processed CSV to S3
    - Save one local inspection copy
    - Push S3 path to XCom
    - Clean up temp files
    """
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    from datetime import datetime
    import logging
    import os
    import pandas as pd

    s3_hook: S3Hook = S3Hook(aws_conn_id='aws_s3')
    task_instance = context['task_instance']

    # Step 0: Extract raw path and generate processed key
    s3_path: str = task_instance.xcom_pull(task_ids="fetch_data", key="raw_s3_path")
    logging.info(f"[s3_path] {s3_path}")

    timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
    logging.info(f"[timestamp] {timestamp}")

    processed_key: str = f"processed/flights_data_{timestamp}.csv"
    logging.info(f"[processed_key] {processed_key}")

    try:
        # Step 1: Download JSON from S3 to a temp file
        json_path: str = download_json_from_s3(s3_path)
        logging.info(f"[json_path] {json_path}")

        # Step 2: Transform the data by adding 'delay_minutes' column
        df: pd.DataFrame = transform_flight_data(json_path)
        logging.info(f"[df.shape] {df.shape}")

        # Step 3: Save transformed DataFrame to a temporary CSV file
        csv_path: str = save_csv_temp(df)
        logging.info(f"[csv_path] {csv_path}")

        # Step 4: Upload the processed CSV to S3
        s3_result: str = upload_file_to_s3(csv_path, processed_key)
        logging.info(f"[s3_result] {s3_result}")

        # Step 5: Save one local inspection copy (and delete older ones)
        inspection_file: str = os.path.basename(processed_key)
        save_local_inspection_copy(df, inspection_file)
        logging.info(f"[local_inspection_file] {inspection_file}")

        # Step 6: Clean up temporary files
        temp_files: list[str] = [json_path, csv_path]
        cleanup_temp_files(temp_files)
        logging.info(f"Cleaned up temp files: {temp_files}")

        # Step 7: Push processed S3 path to XCom
        task_instance.xcom_push(key="processed_s3_path", value=s3_result)
        return s3_result

    except Exception as e:
        logging.error(f"Error in transform_data: {str(e)}")
        raise

# Step 4: Load transformed data into DB
def load_to_db(**kwargs) -> None:
    """
    Load transformed flight data from S3 into PostgreSQL using idempotent upsert logic.


    This function:
    - Pulls the processed S3 path from XCom
    - Downloads the CSV file from S3
    - Parses each row into a tuple format
    - Computes a UUID for each flight using natural keys
    - Loads the data into PostgreSQL with conflict resolution
    - Pushes the number of rows loaded into XCom


    Keyword Args:
    kwargs (dict): Airflow context, including task instance (ti)


    Returns:
    None
    """
    task_instance = kwargs['ti']


    try:
        s3_path: str = task_instance.xcom_pull(task_ids="transform_data", key="processed_s3_path")
        logging.info(f"Processing S3 path: {s3_path}")

        csv_path: str = download_csv_from_s3(s3_path)
        logging.info(f"Downloaded CSV to: {csv_path}")

        df: pd.DataFrame = pd.read_csv(csv_path)
        logging.info(f"Loaded DataFrame with shape: {df.shape}")

        df['flight_id'] = df.apply(compute_flight_uuid, axis=1)
        logging.info(f"Computed UUIDs for {len(df)} flights")

        logging.info(f"Unique flight_id values: {df['flight_id'].nunique()} / Total rows: {len(df)}")

        # Create the flights table if it doesn't exist
        pg_hook = PostgresHook(postgres_conn_id='postgres_airflow')
        create_flights_table_if_not_exists(pg_hook)

        rows_loaded: int = upsert_flight_data(df, pg_hook)
        logging.info(f"Successfully loaded {rows_loaded} rows into PostgreSQL")

        os.remove(csv_path)
        logging.info(f"Cleaned up temporary file: {csv_path}")

        task_instance.xcom_push(key="rows_loaded", value=rows_loaded)


    except Exception as e:                          
        logging.error(f"Error in load_to_db: {str(e)}")
        raise

# ------------------------
# DAG definition
# ------------------------
with DAG(
    dag_id="flight_data_pipeline",
    default_args=default_args,
    description="ETL pipeline for Israel flights dataset",
    schedule="*/15 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["flights", "ETL", "s3"],
) as dag:

    fetch_data_task = PythonOperator(
        task_id="fetch_data",
        python_callable=fetch_data,
    )

    validate_data_task = PythonOperator(
        task_id="validate_data",
        python_callable=validate_data,
    )

    transform_data_task = PythonOperator(
        task_id="transform_data",
        python_callable=transform_data,
    )

    load_to_db_task = PythonOperator(
        task_id="load_to_db",
        python_callable=load_to_db,
        provide_context=True,
    )

    # Define dependencies
    fetch_data_task >> validate_data_task >> transform_data_task >> load_to_db_task

