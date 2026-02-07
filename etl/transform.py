import logging
import pandas as pd

logger = logging.getLogger(__name__)

COLUMN_MAPPING = {
    "CHOPER": "airline_code",
    "CHFLTN": "flight_number",
    "CHOPERD": "airline_name",
    "CHSTOL": "scheduled_departure_time",
    "CHPTOL": "actual_departure_time",
    "CHAORD": "arrival_departure_code",
    "CHLOC1": "airport_code",
    "CHLOC1D": "airport_name_english",
    "CHLOC1TH": "airport_name_hebrew",
    "CHLOC1T": "city_name_english",
    "CHLOC1CH": "country_name_hebrew",
    "CHLOCCT": "country_name_english",
    "CHTERM": "terminal_number",
    "CHCINT": "check_in_time",
    "CHCKZN": "check_in_zone",
    "CHRMINE": "status_english",
    "CHRMINH": "status_hebrew",
}


def transform_records(records: list[dict]) -> pd.DataFrame:
    """
    Transform raw CKAN records into a clean DataFrame.

    - Renames Hebrew column codes to English names
    - Parses scheduled/actual times to datetime
    - Calculates delay_minutes = (actual - scheduled) in minutes
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.rename(columns=COLUMN_MAPPING)

    df["scheduled_departure"] = pd.to_datetime(df["scheduled_departure_time"], errors="coerce")
    df["actual_departure"] = pd.to_datetime(df["actual_departure_time"], errors="coerce")

    df["delay_minutes"] = (
        (df["actual_departure"] - df["scheduled_departure"]).dt.total_seconds() / 60.0
    )

    logger.info("Transformed %d records", len(df))
    return df
