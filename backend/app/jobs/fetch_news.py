import logging
import time

from app.database import SessionLocal
from app.repositories import companies as companies_repository
from app.services import companies as companies_service
from app.sources import gnews

logger = logging.getLogger(__name__)

SECONDS_BETWEEN_REQUESTS = 1.1
# GNews's free plan allows 100 requests a day, so this leaves some for new companies.
DAILY_REQUEST_BUDGET = 80


def fetch_all_companies() -> None:
    with SessionLocal() as db:
        due = companies_repository.list_due_for_refresh(db, DAILY_REQUEST_BUDGET)
        for company in due:
            # One failed company shouldn't stop the others.
            try:
                companies_service.refresh_company(db, company)
                logger.info("Fetched news for %s", company.ticker)
            except gnews.NewsSourceError:
                db.rollback()
                logger.exception("Fetch failed for %s", company.ticker)
            time.sleep(SECONDS_BETWEEN_REQUESTS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetch_all_companies()
