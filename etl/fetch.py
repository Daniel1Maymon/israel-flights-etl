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
    page = 1

    logger.info(
        "Starting paginated fetch from CKAN API — batch_size=%d, resource_id=%s",
        batch_size,
        resource_id,
    )

    while True:
        logger.info(
            "Fetching page %d (offset=%d, limit=%d)...",
            page,
            offset,
            batch_size,
        )
        params = {"resource_id": resource_id, "limit": batch_size, "offset": offset}
        response = requests.get(base_url, params=params, timeout=300)

        if response.status_code != 200:
            logger.error("API request failed with status %d — aborting fetch", response.status_code)
            raise Exception(f"API request failed: {response.status_code}")

        records = response.json()["result"]["records"]

        if not records:
            logger.info(
                "Page %d returned 0 records — reached end of dataset, stopping pagination",
                page,
            )
            break

        all_records.extend(records)
        logger.info(
            "Page %d: got %d records (running total: %d)",
            page,
            len(records),
            len(all_records),
        )

        if len(records) < batch_size:
            logger.info(
                "Page %d returned fewer records than batch_size (%d < %d) — last page, stopping",
                page,
                len(records),
                batch_size,
            )
            break

        offset += batch_size
        page += 1

    logger.info("Fetch complete — %d total records across %d page(s)", len(all_records), page)
    return all_records
