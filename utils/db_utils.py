
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
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    rows_loaded = 0

    try:
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO flights (
                    flight_id, airline_code, flight_number, direction, location_iata,
                    scheduled_time, actual_time, airline_name, location_en, location_he,
                    location_city_en, country_en, country_he, terminal, checkin_counters,
                    checkin_zone, status_en, status_he, delay_minutes, scrape_timestamp, raw_s3_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (flight_id) DO NOTHING
            """, (
                row['flight_id'],
                row.get('airline_code', ''),  # airline_code - IATA code
                row.get('flight_number', ''),  # flight_number
                row.get('arrival_departure_code', ''),  # direction - A=Arrival, D=Departure
                row.get('airport_code', ''),  # location_iata - IATA code
                row.get('scheduled_departure', None),  # scheduled_time
                row.get('actual_departure', None),  # actual_time
                row.get('airline_name', ''),  # airline_name - full airline name
                row.get('airport_name_english', ''),  # location_en - location name in English
                row.get('airport_name_hebrew', ''),  # location_he - location name in Hebrew
                row.get('city_name_english', ''),  # location_city_en - city name
                '',  # country_en - country name in English (not in CSV, will be empty)
                row.get('country_name_english', ''),  # country_he - country name in Hebrew
                row.get('terminal_number', None),  # terminal
                row.get('check_in_time', ''),  # checkin_counters
                row.get('check_in_zone', ''),  # checkin_zone
                row.get('status_english', ''),  # status_en - status in English
                row.get('status_hebrew', ''),  # status_he - status in Hebrew
                row.get('delay_minutes', 0),  # delay_minutes
                pd.Timestamp.now(),  # scrape_timestamp
                f's3://{S3_BUCKET_NAME}/processed/'  # raw_s3_path (placeholder)
            ))
            
            # Count only the rows that were actually inserted (not conflicts)
            if cursor.rowcount > 0:
                rows_loaded += 1

        conn.commit()
        logging.info(f"Upserted {rows_loaded} new rows into flights table")
        return rows_loaded

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during upsert: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()
