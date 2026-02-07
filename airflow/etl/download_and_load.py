"""
Download flight files from S3 and load them into the database.

This module provides functions to:
1. Download flight data files from S3 (both raw JSON and processed CSV)
2. Process the data and insert it into PostgreSQL
3. Handle both gzipped and regular files
4. Use proper identifier keys for deduplication
"""

import logging
import gzip
import json
import tempfile
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import boto3
import psycopg2
from multiprocessing import Pool, cpu_count
from functools import partial
# Airflow imports - only import if available
try:
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook
    from airflow.providers.postgres.hooks.postgres import PostgresHook
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    S3Hook = None
    PostgresHook = None
from config.settings import S3_BUCKET_NAME, S3_RAW_PATH

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, try to load manually
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key] = value


def get_postgres_connection():
    """
    Get a PostgreSQL connection, either from Airflow or direct connection.
    
    Returns:
        psycopg2.connection: PostgreSQL connection object
    """
    if AIRFLOW_AVAILABLE:
        try:
            # Try to use Airflow PostgresHook first
            pg_hook = PostgresHook(postgres_conn_id='postgres_flights')
            return pg_hook.get_conn()
        except Exception as e:
            logging.warning(f"Failed to use Airflow PostgresHook: {e}. Using direct connection.")
    
    # Use direct connection with environment variables
    conn_params = {
        'host': os.getenv('POSTGRES_FLIGHTS_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_FLIGHTS_PORT', '5433')),
        'database': os.getenv('POSTGRES_FLIGHTS_DB', 'flights_db'),
        'user': os.getenv('POSTGRES_FLIGHTS_USER', 'daniel'),
        'password': os.getenv('POSTGRES_FLIGHTS_PASSWORD', 'daniel')
    }
    
    return psycopg2.connect(**conn_params)


def download_gzipped_json_from_s3(bucket_name: str, s3_key: str) -> List[Dict[str, Any]]:
    """
    Download and decompress a gzipped JSON file from S3.
    
    Args:
        bucket_name (str): S3 bucket name
        s3_key (str): S3 object key
        
    Returns:
        List[Dict[str, Any]]: List of flight records
    """
    try:
        # Create S3 client with credentials from environment variables
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # Get the gzipped object from S3
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        
        # Read and decompress the data
        compressed_data = response['Body'].read()
        decompressed_data = gzip.decompress(compressed_data)
        
        # Parse JSON
        json_str = decompressed_data.decode('utf-8')
        records = json.loads(json_str)
        
        logging.info(f'Successfully downloaded and decompressed {len(records)} records from s3://{bucket_name}/{s3_key}')
        return records
        
    except Exception as e:
        logging.error(f'Failed to download gzipped file from s3://{bucket_name}/{s3_key}: {e}')
        raise


def download_json_from_s3_airflow(s3_path: str) -> str:
    """
    Download a JSON file from S3 using Airflow S3Hook (for compatibility with existing DAG).
    
    Args:
        s3_path (str): Full S3 path in format 's3://bucket/key'
        
    Returns:
        str: Local path to downloaded temporary JSON file
    """
    if AIRFLOW_AVAILABLE:
        s3_hook = S3Hook(aws_conn_id='aws_s3')
        s3_clean = s3_path.replace("s3://", "")
        bucket_name, key = s3_clean.split("/", 1)

        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.json', delete=False) as temp_file:
            s3_obj = s3_hook.get_key(bucket_name=bucket_name, key=key)
            s3_obj.download_fileobj(temp_file)
            temp_path = temp_file.name
    else:
        # Fallback to direct boto3 download
        s3_clean = s3_path.replace("s3://", "")
        bucket_name, key = s3_clean.split("/", 1)
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.json', delete=False) as temp_file:
            s3_client.download_fileobj(bucket_name, key, temp_file)
            temp_path = temp_file.name

    logging.info(f"Downloaded JSON from S3 to temporary file: {temp_path}")
    return temp_path


def transform_raw_flight_data(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transform raw flight data from CKAN API format to database format.
    
    Args:
        records (List[Dict[str, Any]]): Raw flight records from API
        
    Returns:
        pd.DataFrame: Transformed DataFrame ready for database insertion
    """
    try:
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Check if DataFrame is empty
        if df.empty:
            logging.warning("Empty DataFrame created from records")
            return df
        
        # Rename columns to match database schema
        column_mapping = {
            'CHOPER': 'airline_code',
            'CHFLTN': 'flight_number', 
            'CHOPERD': 'airline_name',
            'CHSTOL': 'scheduled_departure_time',
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
    
        # Convert time columns to datetime with error handling
        try:
            df["scheduled_departure"] = pd.to_datetime(df["scheduled_departure_time"], errors="coerce")
            df["actual_departure"] = pd.to_datetime(df["actual_departure_time"], errors="coerce")
        except Exception as e:
            logging.warning(f"Error converting datetime columns: {e}")
            df["scheduled_departure"] = pd.NaT
            df["actual_departure"] = pd.NaT
        
        # Calculate delay in minutes with error handling
        try:
            df["delay_minutes"] = (
                (df["actual_departure"] - df["scheduled_departure"])
                .dt.total_seconds() / 60.0
            ).fillna(0).astype(int)
        except Exception as e:
            logging.warning(f"Error calculating delay: {e}")
            df["delay_minutes"] = 0
        
        # Add metadata
        df["scrape_timestamp"] = pd.Timestamp.now()
        df["raw_s3_path"] = f"s3://{S3_BUCKET_NAME}/{S3_RAW_PATH}/latest.json.gz"
        
        return df
        
    except Exception as e:
        logging.error(f"Error in transform_raw_flight_data: {e}")
        raise


def compute_flight_uuid(row: pd.Series) -> str:
    """
    Generate unique flight ID using natural keys for deduplication.
    
    Args:
        row (pd.Series): Flight record row
        
    Returns:
        str: MD5 hash of natural key
    """
    import hashlib
    
    # Extract natural key components
    choper = str(row.get('airline_code', ''))
    chfltn = str(row.get('flight_number', ''))
    chaord = str(row.get('arrival_departure_code', ''))
    chloc1 = str(row.get('airport_code', ''))
    chstol = str(row.get('scheduled_departure', ''))

    # Create natural key
    natural_key = f"{choper}_{chfltn}_{chaord}_{chloc1}_{chstol}"
    
    # Generate MD5 hash
    return hashlib.md5(natural_key.encode()).hexdigest()


def create_flights_table_if_not_exists(conn) -> None:
    """
    Create the flights table if it doesn't exist.
    
    Args:
        conn: PostgreSQL connection object
    """
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flights (
                flight_id VARCHAR(32) PRIMARY KEY,
                airline_code VARCHAR(10),
                flight_number VARCHAR(20),
                direction VARCHAR(1),
                location_iata VARCHAR(10),
                scheduled_time TIMESTAMP,
                actual_time TIMESTAMP,
                airline_name VARCHAR(100),
                location_en VARCHAR(100),
                location_he VARCHAR(100),
                location_city_en VARCHAR(100),
                country_en VARCHAR(100),
                country_he VARCHAR(100),
                terminal VARCHAR(10),
                checkin_counters VARCHAR(100),
                checkin_zone VARCHAR(100),
                status_en VARCHAR(100),
                status_he VARCHAR(100),
                delay_minutes INTEGER,
                scrape_timestamp TIMESTAMP,
                raw_s3_path VARCHAR(500)
            );
        """)
        
        conn.commit()
        logging.info("Flights table created successfully or already exists")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error creating flights table: {str(e)}")
        raise
    finally:
        cursor.close()


def upsert_flight_data(df: pd.DataFrame, conn) -> int:
    """
    Insert flight data into PostgreSQL with conflict resolution using bulk operations.
    
    Args:
        df (pd.DataFrame): Flight data DataFrame
        conn: PostgreSQL connection object
        
    Returns:
        int: Number of rows actually inserted (not skipped due to conflicts)
    """
    if df.empty:
        logging.warning("DataFrame is empty, nothing to upsert")
        return 0
        
    cursor = conn.cursor()
    rows_loaded = 0

    try:
        # Prepare data for bulk insert
        df_clean = df.copy()
        
        # Fill missing values and convert types
        df_clean['airline_code'] = df_clean.get('airline_code', '').fillna('')
        df_clean['flight_number'] = df_clean.get('flight_number', '').fillna('')
        df_clean['arrival_departure_code'] = df_clean.get('arrival_departure_code', '').fillna('')
        df_clean['airport_code'] = df_clean.get('airport_code', '').fillna('')
        df_clean['airline_name'] = df_clean.get('airline_name', '').fillna('')
        df_clean['airport_name_english'] = df_clean.get('airport_name_english', '').fillna('')
        df_clean['airport_name_hebrew'] = df_clean.get('airport_name_hebrew', '').fillna('')
        df_clean['city_name_english'] = df_clean.get('city_name_english', '').fillna('')
        df_clean['country_name_english'] = df_clean.get('country_name_english', '').fillna('')
        df_clean['country_name_hebrew'] = df_clean.get('country_name_hebrew', '').fillna('')
        df_clean['check_in_time'] = df_clean.get('check_in_time', '').fillna('')
        df_clean['check_in_zone'] = df_clean.get('check_in_zone', '').fillna('')
        df_clean['status_english'] = df_clean.get('status_english', '').fillna('')
        df_clean['status_hebrew'] = df_clean.get('status_hebrew', '').fillna('')
        df_clean['delay_minutes'] = df_clean.get('delay_minutes', 0).fillna(0).astype(int)
        df_clean['scrape_timestamp'] = df_clean.get('scrape_timestamp', pd.Timestamp.now())
        df_clean['raw_s3_path'] = df_clean.get('raw_s3_path', f's3://{S3_BUCKET_NAME}/{S3_RAW_PATH}/latest.json.gz')
        
        # Convert DataFrame to list of tuples for bulk insert (avoid iterrows)
        # Convert numpy types to Python native types for psycopg2 compatibility
        data_tuples = []
        for i in range(len(df_clean)):
            row = df_clean.iloc[i]
            data_tuples.append((
                str(row['flight_id']),  # Ensure string
                str(row['airline_code']),
                str(row['flight_number']),
                str(row['arrival_departure_code']),
                str(row['airport_code']),
                row.get('scheduled_departure', None),
                row.get('actual_departure', None),
                str(row['airline_name']),
                str(row['airport_name_english']),
                str(row['airport_name_hebrew']),
                str(row['city_name_english']),
                str(row['country_name_english']),
                str(row['country_name_hebrew']),
                str(row.get('terminal_number', None)) if pd.notna(row.get('terminal_number', None)) else None,
                str(row['check_in_time']),
                str(row['check_in_zone']),
                str(row['status_english']),
                str(row['status_hebrew']),
                int(row['delay_minutes']),  # Convert numpy.int64 to Python int
                row['scrape_timestamp'],
                str(row['raw_s3_path'])
            ))
        
        # Use executemany for bulk insert (much faster than individual INSERTs)
        cursor.executemany("""
                INSERT INTO flights (
                    flight_id, airline_code, flight_number, direction, location_iata,
                    scheduled_time, actual_time, airline_name, location_en, location_he,
                    location_city_en, country_en, country_he, terminal, checkin_counters,
                    checkin_zone, status_en, status_he, delay_minutes, scrape_timestamp, raw_s3_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (flight_id) DO UPDATE SET
                    actual_time = EXCLUDED.actual_time,
                    status_en = EXCLUDED.status_en,
                    status_he = EXCLUDED.status_he,
                    delay_minutes = EXCLUDED.delay_minutes,
                    country_en = EXCLUDED.country_en,
                    country_he = EXCLUDED.country_he,
                    scrape_timestamp = EXCLUDED.scrape_timestamp,
                    raw_s3_path = EXCLUDED.raw_s3_path
        """, data_tuples)
        
        rows_loaded = len(data_tuples)
        conn.commit()
        logging.info(f"Upserted {rows_loaded} rows into flights table (inserted new or updated existing)")
        return rows_loaded

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during upsert: {str(e)}")
        raise
    finally:
        cursor.close()


def create_processed_files_table_if_not_exists(conn) -> None:
    """
    Create the processed_files table if it doesn't exist.
    
    Args:
        conn: PostgreSQL connection object
    """
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                file_name VARCHAR(255) PRIMARY KEY,
                s3_key VARCHAR(500) NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'success'
            );
        """)
        
        conn.commit()
        logging.info("Processed files table created successfully or already exists")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error creating processed_files table: {str(e)}")
        raise
    finally:
        cursor.close()


def is_file_processed(conn, file_name: str) -> bool:
    """
    Check if a file has already been processed successfully.
    
    Args:
        conn: PostgreSQL connection object
        file_name: Name of the file to check
        
    Returns:
        bool: True if file was processed successfully, False otherwise
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT status FROM processed_files WHERE file_name = %s",
            (file_name,)
        )
        result = cursor.fetchone()
        return result is not None and result[0] == 'success'
    except Exception as e:
        logging.error(f"Error checking if file is processed: {e}")
        return False
    finally:
        cursor.close()


def mark_file_processed(conn, file_name: str, s3_key: str, status: str = 'success') -> None:
    """
    Mark a file as processed in the database.
    
    Args:
        conn: PostgreSQL connection object
        file_name: Name of the file
        s3_key: S3 key/path of the file
        status: Processing status ('success' or 'failed')
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO processed_files (file_name, s3_key, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (file_name) 
            DO UPDATE SET 
                s3_key = EXCLUDED.s3_key,
                processed_at = CURRENT_TIMESTAMP,
                status = EXCLUDED.status
        """, (file_name, s3_key, status))
        conn.commit()
        logging.info(f"Marked file {file_name} as {status}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error marking file as processed: {e}")
        raise
    finally:
        cursor.close()


def get_processed_files_status(conn) -> List[Dict[str, Any]]:
    """
    Get the status of all processed files.
    
    Args:
        conn: PostgreSQL connection object
        
    Returns:
        List[Dict]: List of processed files with their status
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT file_name, s3_key, processed_at, status
            FROM processed_files
            ORDER BY processed_at DESC
        """)
        results = cursor.fetchall()
        
        return [
            {
                'file_name': row[0],
                's3_key': row[1],
                'processed_at': row[2],
                'status': row[3]
            }
            for row in results
        ]
    except Exception as e:
        logging.error(f"Error getting processed files status: {e}")
        return []
    finally:
        cursor.close()


def download_and_load_from_s3(
    bucket_name: str = S3_BUCKET_NAME,
    s3_key: str = None,
    use_gzipped: bool = True,
    pg_conn_id: str = 'postgres_flights',
    force: bool = False
) -> Dict[str, Any]:
    """
    Main function to download flight data from S3 and load it into the database.
    
    Args:
        bucket_name (str): S3 bucket name
        s3_key (str): S3 object key (if None, uses latest.json.gz)
        use_gzipped (bool): Whether to expect gzipped files
        pg_conn_id (str): Airflow PostgreSQL connection ID
        
    Returns:
        Dict[str, Any]: Results summary including rows loaded, processing time, etc.
    """
    start_time = datetime.now()
    
    try:
        # Determine S3 key
        if s3_key is None:
            s3_key = f"{S3_RAW_PATH}/latest.json.gz"
        
        logging.info(f"Starting download and load process for s3://{bucket_name}/{s3_key}")
        file_name = s3_key.split('/')[-1]
        logging.info(f"File name: {file_name}")
        
        # Step 1: Download data from S3
        if use_gzipped and s3_key.endswith('.gz'):
            records = download_gzipped_json_from_s3(bucket_name, s3_key)
        else:
            # For non-gzipped files, use Airflow S3Hook
            s3_path = f"s3://{bucket_name}/{s3_key}"
            json_path = download_json_from_s3_airflow(s3_path)
            with open(json_path, 'r') as f:
                records = json.load(f)
            os.remove(json_path)  # Clean up temp file
        
        logging.info(f"Downloaded {len(records)} records from S3")
        
        # Step 2: Transform data
        df = transform_raw_flight_data(records)
        logging.info(f"Transformed data into DataFrame with shape: {df.shape}")
        
        # Step 3: Generate flight IDs for deduplication
        df['flight_id'] = df.apply(compute_flight_uuid, axis=1)
        logging.info(f"Generated {df['flight_id'].nunique()} unique flight IDs")
        
        # Step 4: Set up database connection
        conn = get_postgres_connection()
        
        try:
        # Step 5: Create table if not exists
            create_flights_table_if_not_exists(conn)
            create_processed_files_table_if_not_exists(conn)

            # Step 5B: Skip if already processed (unless force=True)
            if not force and is_file_processed(conn, file_name):
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                skipped_result = {
                    "status": "skipped",
                    "total_records": 0,
                    "rows_loaded": 0,
                    "rows_skipped": 0,
                    "processing_time_seconds": processing_time,
                    "s3_source": f"s3://{bucket_name}/{s3_key}",
                    "timestamp": end_time.isoformat()
                }
                logging.info(f"Skipping {s3_key} - already processed")
                return skipped_result
        
        # Step 6: Load data into database
            rows_loaded = upsert_flight_data(df, conn)
            mark_file_processed(conn, file_name, s3_key, 'success')
        finally:
            conn.close()
        
        # Calculate processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        result = {
            "status": "success",
            "total_records": len(records),
            "rows_loaded": rows_loaded,
            "rows_skipped": len(records) - rows_loaded,
            "processing_time_seconds": processing_time,
            "s3_source": f"s3://{bucket_name}/{s3_key}",
            "timestamp": end_time.isoformat()
        }
        
        logging.info(f"Successfully completed download and load: {result}")
        return result
        
    except Exception as e:
        try:
            conn = get_postgres_connection()
            try:
                file_name = s3_key.split('/')[-1] if s3_key else "unknown"
                create_processed_files_table_if_not_exists(conn)
                mark_file_processed(conn, file_name, s3_key or "unknown", 'failed')
            finally:
                conn.close()
        except Exception:
            logging.exception("Failed to mark file as failed")

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        error_result = {
            "status": "error",
            "error_message": str(e),
            "processing_time_seconds": processing_time,
            "s3_source": f"s3://{bucket_name}/{s3_key}",
            "timestamp": end_time.isoformat()
        }
        
        logging.error(f"Download and load failed: {error_result}")
        raise


def download_and_load_latest() -> Dict[str, Any]:
    """
    Convenience function to download and load the latest flight data.
    
    Returns:
        Dict[str, Any]: Results summary
    """
    return download_and_load_from_s3(
        bucket_name=S3_BUCKET_NAME,
        s3_key=f"{S3_RAW_PATH}/latest.json.gz",
        use_gzipped=True
    )


def process_single_file(args):
    """
    Process a single S3 file. This function is designed to be used with multiprocessing.
    
    Args:
        args: Tuple of (s3_key, bucket_name, s3_client_config)
        
    Returns:
        Dict with processing results for this file
    """
    s3_key, bucket_name, s3_config = args
    
    try:
        # Create S3 client for this process
        s3 = boto3.client('s3', **s3_config)
        
        # Download and process the file
        if s3_key.endswith('.gz'):
            records = download_gzipped_json_from_s3(bucket_name, s3_key)
        else:
            response = s3.get_object(Bucket=bucket_name, Key=s3_key)
            content = response['Body'].read().decode('utf-8')
            records = json.loads(content)
        
        if not records or len(records) == 0:
            return {
                's3_key': s3_key,
                'status': 'skipped',
                'records': 0,
                'rows_loaded': 0,
                'error': 'No records found'
            }
        
        # Transform the data
        df = transform_raw_flight_data(records)
        df['flight_id'] = df.apply(compute_flight_uuid, axis=1)
        
        # Get database connection for this process
        conn = get_postgres_connection()
        try:
            # Create table if it doesn't exist
            create_flights_table_if_not_exists(conn)
            
            # Upsert to database
            rows_loaded = upsert_flight_data(df, conn)
            
            return {
                's3_key': s3_key,
                'status': 'success',
                'records': len(records),
                'rows_loaded': rows_loaded,
                'error': None
            }
        finally:
            conn.close()
            
    except Exception as e:
        return {
            's3_key': s3_key,
            'status': 'error',
            'records': 0,
            'rows_loaded': 0,
            'error': str(e)
        }


def download_and_load_all_files(
    bucket_name: str = S3_BUCKET_NAME,
    prefix: str = None,
    pg_conn_id: str = 'postgres_flights',
    max_workers: int = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Download and process ALL flight data files from S3 and load them into the database using parallel processing.
    
    Args:
        bucket_name (str): S3 bucket name
        prefix (str): S3 prefix to filter files (e.g., 'uploads/', 'raw/flights/')
        pg_conn_id (str): Airflow PostgreSQL connection ID
        max_workers (int): Maximum number of parallel workers (default: CPU count)
        
    Returns:
        Dict[str, Any]: Results summary including total files processed, rows loaded, etc.
    """
    start_time = datetime.now()
    
    try:
        # Create S3 client with credentials from environment variables
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # List all files in the bucket with the given prefix
        if prefix is None:
            prefix = f"{S3_RAW_PATH}/"
        
        logging.info(f"Listing all files in s3://{bucket_name}/{prefix}")
        
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        all_files = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Only process JSON files
                    if obj['Key'].endswith('.json') or obj['Key'].endswith('.json.gz'):
                        all_files.append(obj['Key'])
        
        # Sort files by modification time (oldest first)
        all_files.sort()
        
        logging.info(f"Found {len(all_files)} files to process")
        
        # Set up database connection to create tables
        conn = get_postgres_connection()
        try:
            create_flights_table_if_not_exists(conn)
            create_processed_files_table_if_not_exists(conn)
        finally:
            conn.close()
        
        # Process files with tracking
        total_records = 0
        total_rows_loaded = 0
        files_processed = 0
        files_failed = 0
        files_skipped = 0
        
        for i, s3_key in enumerate(all_files):
            file_name = s3_key.split('/')[-1]  # Get just the filename
            logging.info(f"Processing file {i+1}/{len(all_files)}: {s3_key}")
            
            # Check if file already processed (unless force=True)
            conn = get_postgres_connection()
            try:
                logging.info(f"Checking processed_files for file_name={file_name} (s3_key={s3_key})")
                if not force and is_file_processed(conn, file_name):
                    logging.info(f"Skipping {s3_key} - already processed")
                    files_skipped += 1
                    continue
            finally:
                conn.close()
            
            # Process the file
            try:
                # Download and process the file
                if s3_key.endswith('.gz'):
                    records = download_gzipped_json_from_s3(bucket_name, s3_key)
                else:
                    s3_path = f"s3://{bucket_name}/{s3_key}"
                    json_path = download_json_from_s3_airflow(s3_path)
                    with open(json_path, 'r') as f:
                        records = json.load(f)
                    os.remove(json_path)
                
                if not records or len(records) == 0:
                    logging.warning(f"No records found in {s3_key}, skipping")
                    files_skipped += 1
                    continue
                
                # Transform and load data
                df = transform_raw_flight_data(records)
                df['flight_id'] = df.apply(compute_flight_uuid, axis=1)
                
                conn = get_postgres_connection()
                try:
                    rows_loaded = upsert_flight_data(df, conn)
                    mark_file_processed(conn, file_name, s3_key, 'success')
                finally:
                    conn.close()
                
                total_records += len(records)
                total_rows_loaded += rows_loaded
                files_processed += 1
                logging.info(f"Processed {s3_key}: {len(records)} records, {rows_loaded} rows loaded")
                
            except Exception as e:
                logging.error(f"Failed to process {s3_key}: {str(e)}")
                files_failed += 1
                
                # Mark as failed in database
                conn = get_postgres_connection()
                try:
                    mark_file_processed(conn, file_name, s3_key, 'failed')
                finally:
                    conn.close()
                continue
        
        # Calculate processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        result = {
            "status": "success",
            "files_processed": files_processed,
            "files_failed": files_failed,
            "files_skipped": files_skipped,
            "total_files": len(all_files),
            "total_records": total_records,
            "rows_loaded": total_rows_loaded,
            "rows_skipped": total_records - total_rows_loaded,
            "processing_time_seconds": processing_time,
            "s3_source": f"s3://{bucket_name}/{prefix}",
            "timestamp": end_time.isoformat(),
            "parallel_workers": max_workers
        }
        
        logging.info(f"Successfully completed processing all files: {result}")
        return result
        
    except Exception as e:
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        error_result = {
            "status": "error",
            "error_message": str(e),
            "processing_time_seconds": processing_time,
            "s3_source": f"s3://{bucket_name}/{prefix}",
            "timestamp": end_time.isoformat()
        }
        
        logging.error(f"Processing all files failed: {error_result}")
        raise


if __name__ == "__main__":
    # Test the function locally
    logging.basicConfig(level=logging.INFO)
    
    try:
        result = download_and_load_latest()
        print(f"Test completed successfully: {result}")
    except Exception as e:
        print(f"Test failed: {e}")
