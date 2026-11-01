import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.jobs.fetch_news import fetch_all_companies
from app.jobs.load_listed_companies import load_listed_companies

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("America/Toronto")
RUN_HOUR = 7


def seconds_until_next_run(now: datetime) -> float:
    next_run = now.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()


def main() -> None:
    while True:
        wait = seconds_until_next_run(datetime.now(TIMEZONE))
        logger.info("Next news fetch in %.0f seconds", wait)
        time.sleep(wait)
        try:
            load_listed_companies()
            fetch_all_companies()
        except Exception:
            logger.exception("Morning jobs failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
