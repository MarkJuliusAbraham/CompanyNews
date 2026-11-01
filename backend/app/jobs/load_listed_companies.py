import logging

from app.database import SessionLocal
from app.repositories import companies as companies_repository
from app.sources import nasdaq

logger = logging.getLogger(__name__)

# Far fewer rows than this means the download is wrong, so keep the current list.
MINIMUM_EXPECTED = 1000


def load_listed_companies() -> None:
    try:
        companies = nasdaq.fetch_listed_companies()
    except nasdaq.ListingSourceError:
        logger.exception("Could not refresh the ticker list")
        return
    if len(companies) < MINIMUM_EXPECTED:
        logger.error("Ticker list only had %s rows, so it was skipped", len(companies))
        return

    with SessionLocal() as db:
        companies_repository.replace_listed(db, companies)
        db.commit()
    logger.info("Loaded %s listed companies", len(companies))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_listed_companies()
