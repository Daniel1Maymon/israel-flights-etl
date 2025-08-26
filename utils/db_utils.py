
import logging
import hashlib
import tempfile
import pandas as pd
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values
from .init_airline_db import createFlightsTable


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
    airline_code = row.get('CHOPER', '')
    flight_number = row.get('CHFLTN', '')
    direction = row.get('CHAORD', '')
    location_iata = row.get('CHLOC1', '')
    scheduled_departure = row.get('CHSTOL', '')

    natural_key = f"{airline_code}_{flight_number}_{direction}_{location_iata}_{scheduled_departure}"
    return hashlib.md5(natural_key.encode()).hexdigest()


def create_flights_table_if_not_exists(pg_hook: PostgresHook) -> None:
    conn = pg_hook.get_conn()
    pg_dsn = pg_hook.get_uri()
    
    try:
        # Call the existing createFlightsTable function
        createFlightsTable(pg_dsn)
        logging.info("Flights table checked/created successfully using createFlightsTable")
        
    except Exception as e:
        logging.error(f"Error creating flights table: {str(e)}")
        raise
    finally:
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
                row.get('CHOPER', ''),  # airline_code - IATA code
                row.get('CHFLTN', ''),  # flight_number
                row.get('CHAORD', ''),  # direction - A=Arrival, D=Departure
                row.get('CHLOC1', ''),  # location_iata - IATA code
                row.get('CHSTOL', ''),  # scheduled_time
                row.get('CHPTOL', ''),  # actual_time
                row.get('CHOPERD', ''),  # airline_name - full airline name
                row.get('CHLOC1D', ''),  # location_en - location name in English
                row.get('CHLOC1TH', ''),  # location_he - location name in Hebrew
                row.get('CHLOC1T', ''),  # location_city_en - city name
                '',  # country_en - country name in English (not in CSV, will be empty)
                row.get('CHLOCCT', ''),  # country_he - country name in Hebrew
                row.get('CHTERM', None),  # terminal
                row.get('CHCINT', ''),  # checkin_counters
                row.get('CHCKZN', ''),  # checkin_zone
                row.get('CHRMINE', ''),  # status_en - status in English
                row.get('CHRMINH', ''),  # status_he - status in Hebrew
                row.get('delay_minutes', 0),  # delay_minutes
                pd.Timestamp.now(),  # scrape_timestamp
                's3://bbucket2/processed/'  # raw_s3_path (placeholder)
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
