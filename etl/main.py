import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from etl.config import get_config
from etl.fetch import fetch_flights
from etl.transform import transform_records
from etl.load import load_to_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    """Execute one fetch → transform → load cycle."""
    cfg = get_config()

    logger.info("Starting ETL pipeline run")

    records = fetch_flights(
        base_url=cfg["ckan_base_url"],
        resource_id=cfg["ckan_resource_id"],
        batch_size=cfg["ckan_batch_size"],
    )

    if not records:
        logger.info("No records fetched — skipping transform/load")
        return

    df = transform_records(records)

    rows = load_to_db(df, cfg)
    logger.info("Pipeline run complete — %d rows upserted", rows)


def main() -> None:
    """Entry point: run once immediately, then schedule every N minutes."""
    cfg = get_config()
    interval = cfg["schedule_interval_minutes"]

    # Run immediately on startup
    try:
        run_pipeline()
    except Exception:
        logger.exception("Initial pipeline run failed")

    # Schedule recurring runs
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "interval", minutes=interval)
    logger.info("Scheduled pipeline to run every %d minutes", interval)

    # Graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Received signal %s — shutting down", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    scheduler.start()


if __name__ == "__main__":
    main()
