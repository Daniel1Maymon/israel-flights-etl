
import logging
import hashlib
import tempfile
import pandas as pd
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values
from config.settings import S3_BUCKET_NAME

def download_csv_from_s3(s3_path: str) -> str:
    s3_hook: S3Hook = S3Hook(aws_conn_id='aws_s3')
    s3_clean: str = s3_path.replace("s3://", "")
    bucket_name, key = s3_clean.split("/", 1)

    with tempfile.NamedTemporaryFile(mode='w+b', suffix='.csv', delete=False) as temp_file:
        s3_obj = s3_hook.get_key(bucket_name=bucket_name, key=key)
        s3_obj.download_fileobj(temp_file)
        temp_path: str = temp_file.name

    logging.info(f"Downloaded CSV from S3 to temporary file: {temp_path}")
    return temp_path


def compute_flight_uuid(row: pd.Series) -> str:
    airline_code = row.get('airline_code', '')
    flight_number = row.get('flight_number', '')
    direction = row.get('arrival_departure_code', '')
    location_iata = row.get('airport_code', '')
    scheduled_departure = row.get('scheduled_departure', None)

    natural_key = f"{airline_code}_{flight_number}_{direction}_{location_iata}_{scheduled_departure}"
    return hashlib.md5(natural_key.encode()).hexdigest()


def create_flights_table_if_not_exists(pg_hook: PostgresHook) -> None:
    """
    Creates the flights table if it doesn't exist using the PostgresHook connection.
    """
    conn = pg_hook.get_conn()
    
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
        logging.info("Flights table created successfully")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error creating flights table: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


def upsert_flight_data(df: pd.DataFrame, pg_hook: PostgresHook) -> int:
    """
    Insert flight data into PostgreSQL with conflict resolution using bulk operations.
    
    Args:
        df (pd.DataFrame): Flight data DataFrame
        pg_hook: PostgreSQL hook object
        
    Returns:
        int: Number of rows actually inserted (not skipped due to conflicts)
    """
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    try:
        # Convert DataFrame to list of tuples for bulk insert (avoid iterrows)
        data_tuples = []
        for i in range(len(df)):
            row = df.iloc[i]
            data_tuples.append((
                str(row['flight_id']),
                str(row.get('airline_code', '')),
                str(row.get('flight_number', '')),
                str(row.get('arrival_departure_code', '')),
                str(row.get('airport_code', '')),
                row.get('scheduled_departure', None),
                row.get('actual_departure', None),
                str(row.get('airline_name', '')),
                str(row.get('airport_name_english', '')),
                str(row.get('airport_name_hebrew', '')),
                str(row.get('city_name_english', '')),
                str(row.get('country_name_english', '')),
                str(row.get('country_name_hebrew', '')),
                int(row.get('terminal_number', 0)) if pd.notna(row.get('terminal_number', 0)) else None,
                str(row.get('check_in_time', '')),
                str(row.get('check_in_zone', '')),
                str(row.get('status_english', '')),
                str(row.get('status_hebrew', '')),
                int(row.get('delay_minutes', 0)) if pd.notna(row.get('delay_minutes', 0)) else 0,
                pd.Timestamp.now(),
                f's3://{S3_BUCKET_NAME}/processed/'
            ))

        # Bulk insert with conflict resolution - update dynamic fields if flight exists
        cursor.executemany("""
            INSERT INTO flights (
                flight_id, airline_code, flight_number, direction, location_iata,
                scheduled_time, actual_time, airline_name, location_en, location_he,
                location_city_en, country_en, country_he, terminal, checkin_counters,
                checkin_zone, status_en, status_he, delay_minutes, scrape_timestamp, raw_s3_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (flight_id) DO UPDATE SET
                actual_time = COALESCE(EXCLUDED.actual_time, flights.actual_time),
                terminal = EXCLUDED.terminal,
                checkin_counters = EXCLUDED.checkin_counters,
                checkin_zone = EXCLUDED.checkin_zone,
                status_en = EXCLUDED.status_en,
                status_he = EXCLUDED.status_he,
                delay_minutes = CASE 
                    WHEN EXCLUDED.actual_time IS NOT NULL AND flights.scheduled_time IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (EXCLUDED.actual_time - flights.scheduled_time)) / 60
                    ELSE flights.delay_minutes
                END,
                scrape_timestamp = EXCLUDED.scrape_timestamp,
                raw_s3_path = EXCLUDED.raw_s3_path
        """, data_tuples)

        conn.commit()
        
        # Count actual inserts vs updates by checking what changed
        cursor.execute("SELECT COUNT(*) FROM flights WHERE scrape_timestamp >= %s", (pd.Timestamp.now() - pd.Timedelta(minutes=1),))
        recent_updates = cursor.fetchone()[0]
        
        rows_processed = len(data_tuples)
        logging.info(f"Processed {rows_processed} rows into flights table (inserted new or updated existing)")
        logging.info(f"Recent updates in last minute: {recent_updates}")
        
        return rows_processed

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during upsert: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()
