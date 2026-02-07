import hashlib
import logging
import pandas as pd
import psycopg2

logger = logging.getLogger(__name__)


def get_pg_connection(cfg: dict):
    """Create a psycopg2 connection from config dict."""
    return psycopg2.connect(
        host=cfg["pg_host"],
        port=cfg["pg_port"],
        database=cfg["pg_database"],
        user=cfg["pg_user"],
        password=cfg["pg_password"],
    )


def compute_flight_uuid(row: pd.Series) -> str:
    """Generate a unique flight ID (MD5) from natural key components."""
    natural_key = "{}_{}_{}_{}_{}" .format(
        row.get("airline_code", ""),
        row.get("flight_number", ""),
        row.get("arrival_departure_code", ""),
        row.get("airport_code", ""),
        row.get("scheduled_departure", ""),
    )
    return hashlib.md5(natural_key.encode()).hexdigest()


def create_flights_table_if_not_exists(conn) -> None:
    """Create the flights table if it doesn't already exist."""
    cursor = conn.cursor()
    try:
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
                scheduled_departure_time VARCHAR(50),
                actual_departure_time VARCHAR(50)
            );
        """)
        conn.commit()
        logger.info("Flights table ready")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def upsert_flight_data(df: pd.DataFrame, conn) -> int:
    """
    Upsert flight rows into PostgreSQL.

    Uses INSERT ... ON CONFLICT (flight_id) DO UPDATE SET to ensure
    idempotent writes.

    Returns the number of rows upserted.
    """
    if df.empty:
        logger.warning("Empty DataFrame — nothing to upsert")
        return 0

    cursor = conn.cursor()
    try:
        data_tuples = []
        for i in range(len(df)):
            row = df.iloc[i]
            data_tuples.append((
                str(row["flight_id"]),
                str(row.get("airline_code", "")),
                str(row.get("flight_number", "")),
                str(row.get("arrival_departure_code", "")),
                str(row.get("airport_code", "")),
                row.get("scheduled_departure") if pd.notna(row.get("scheduled_departure")) else None,
                row.get("actual_departure") if pd.notna(row.get("actual_departure")) else None,
                str(row.get("airline_name", "")),
                str(row.get("airport_name_english", "")),
                str(row.get("airport_name_hebrew", "")),
                str(row.get("city_name_english", "")),
                str(row.get("country_name_english", "")),
                str(row.get("country_name_hebrew", "")),
                str(row.get("terminal_number", "")) if pd.notna(row.get("terminal_number")) else None,
                str(row.get("check_in_time", "")),
                str(row.get("check_in_zone", "")),
                str(row.get("status_english", "")),
                str(row.get("status_hebrew", "")),
                int(row["delay_minutes"]) if pd.notna(row.get("delay_minutes")) else None,
                str(row.get("scheduled_departure_time", "")),
                str(row.get("actual_departure_time", "")),
            ))

        cursor.executemany("""
            INSERT INTO flights (
                flight_id, airline_code, flight_number, direction, location_iata,
                scheduled_time, actual_time, airline_name, location_en, location_he,
                location_city_en, country_en, country_he, terminal, checkin_counters,
                checkin_zone, status_en, status_he, delay_minutes,
                scheduled_departure_time, actual_departure_time
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (flight_id) DO UPDATE SET
                actual_time = EXCLUDED.actual_time,
                status_en = EXCLUDED.status_en,
                status_he = EXCLUDED.status_he,
                delay_minutes = EXCLUDED.delay_minutes,
                actual_departure_time = EXCLUDED.actual_departure_time
        """, data_tuples)

        rows = len(data_tuples)
        conn.commit()
        logger.info("Upserted %d rows", rows)
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def load_to_db(df: pd.DataFrame, cfg: dict) -> int:
    """
    Full load step: compute UUIDs, ensure table exists, upsert.

    Returns number of rows loaded.
    """
    df["flight_id"] = df.apply(compute_flight_uuid, axis=1)
    logger.info("Computed %d flight UUIDs (%d unique)", len(df), df["flight_id"].nunique())

    conn = get_pg_connection(cfg)
    try:
        create_flights_table_if_not_exists(conn)
        return upsert_flight_data(df, conn)
    finally:
        conn.close()
