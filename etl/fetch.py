import logging
import requests

logger = logging.getLogger(__name__)


def fetch_flights(base_url: str, resource_id: str, batch_size: int = 1000) -> list[dict]:
    """
    Fetch all flight records from the CKAN API using pagination.

    Returns a list of raw record dicts.
    """
    all_records: list[dict] = []
    offset = 0

    while True:
        params = {"resource_id": resource_id, "limit": batch_size, "offset": offset}
        response = requests.get(base_url, params=params, timeout=300)

        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code}")

        records = response.json()["result"]["records"]
        if not records:
            break

        all_records.extend(records)
        offset += batch_size
        logger.info("Fetched %d records (total: %d)", len(records), len(all_records))

    logger.info("Fetch complete — %d records total", len(all_records))
    return all_records
