import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, ListedCompany
from app.repositories import companies as companies_repository
from app.schemas.news import FetchedArticle
from app.services.news_queries import build_query, is_ambiguous, mentions_company
from app.sources import gnews

logger = logging.getLogger(__name__)

FETCH_WINDOW = timedelta(hours=24)
AMBIGUOUS_FIRST_FETCH_WINDOW = timedelta(days=7)

LEGAL_ENDING = re.compile(
    r"[,\s]+(?:Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|Limited|LLC|PLC|Co\.?"
    r"|Company|N\.V\.|S\.A\.|Holdings?)$",
    re.IGNORECASE,
)


class CompanyNotListedError(Exception):
    pass


def to_search_name(name: str) -> str:
    """Turn 'United Airlines Holdings, Inc.' into 'United Airlines'."""
    shorter = LEGAL_ENDING.sub("", name)
    while shorter != name:
        name = shorter
        shorter = LEGAL_ENDING.sub("", name)
    return name


def is_relevant(article: FetchedArticle, company: Company) -> bool:
    text = f"{article.title} {article.description}"
    return mentions_company(text, company.ticker, company.search_name)


def add_company(db: Session, ticker: str) -> tuple[Company, bool]:
    """Return the company and whether it was newly added."""
    existing = companies_repository.get_by_ticker(db, ticker)
    if existing:
        return existing, False

    listed = db.get(ListedCompany, ticker)
    if listed is None:
        raise CompanyNotListedError(ticker)

    company = Company(
        ticker=listed.ticker, name=listed.name, search_name=to_search_name(listed.name)
    )
    db.add(company)
    try:
        db.commit()
    except IntegrityError:
        # Another request added the same company first.
        db.rollback()
        return companies_repository.get_by_ticker(db, ticker), False

    # The company stays saved if this fails, and the morning job fills it in.
    try:
        refresh_company(db, company)
    except gnews.NewsSourceError:
        logger.exception("First fetch failed for %s", company.ticker)
    return company, True


def get_guest_companies(db: Session, tickers: list[str]) -> list[Company]:
    """Return a guest's companies, adding new ones and noting the guest's interest."""
    companies = []
    for ticker in dict.fromkeys(tickers):
        try:
            company, _ = add_company(db, ticker)
        except CompanyNotListedError:
            logger.warning("Guest asked for unlisted ticker %s", ticker)
            continue
        company.last_requested_at = datetime.now(UTC)
        db.commit()
        companies.append(company)
    return companies


def refresh_company(db: Session, company: Company) -> None:
    now = datetime.now(UTC)
    # The ticker rule finds few articles, so these companies would often start empty.
    is_first_fetch = company.last_fetched_at is None
    window = (
        AMBIGUOUS_FIRST_FETCH_WINDOW
        if is_first_fetch and is_ambiguous(company.ticker)
        else FETCH_WINDOW
    )
    query = build_query(company.ticker, company.search_name)
    found = gnews.search_articles(query, since=now - window)
    relevant = [a for a in found if is_relevant(a, company)]
    companies_repository.save_articles(db, company.id, relevant)
    company.last_fetched_at = now
    db.commit()
