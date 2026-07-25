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
        logger.warning("transform_records called with empty records list — returning empty DataFrame")
        return pd.DataFrame()

    logger.info("Transforming %d raw records", len(records))

    df = pd.DataFrame(records)
    logger.info("Renaming %d CKAN column codes to English field names", len(COLUMN_MAPPING))
    df = df.rename(columns=COLUMN_MAPPING)

    logger.info("Parsing scheduled and actual departure times to datetime")
    df["scheduled_departure"] = pd.to_datetime(df["scheduled_departure_time"], errors="coerce")
    df["actual_departure"] = pd.to_datetime(df["actual_departure_time"], errors="coerce")

    sched_nulls = df["scheduled_departure"].isna().sum()
    actual_nulls = df["actual_departure"].isna().sum()
    if sched_nulls:
        logger.warning("%d rows have unparseable scheduled_departure_time", sched_nulls)
    if actual_nulls:
        logger.warning("%d rows have unparseable actual_departure_time — delay_minutes will be null for these", actual_nulls)

    logger.info("Calculating delay_minutes = (actual_departure - scheduled_departure) in minutes")
    df["delay_minutes"] = (
        (df["actual_departure"] - df["scheduled_departure"]).dt.total_seconds() / 60.0
    )

    delay_nulls = df["delay_minutes"].isna().sum()
    delayed = (df["delay_minutes"] > 0).sum()
    logger.info(
        "Transform complete — %d records | delayed: %d | delay unknown: %d",
        len(df),
        delayed,
        delay_nulls,
    )
    return df
