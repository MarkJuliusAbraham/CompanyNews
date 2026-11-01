import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session

from app.models import Article, Company, ListedCompany, TrackedCompany
from app.schemas.news import FetchedArticle, ListedCompanyData

SEARCH_LIMIT = 8
# Keep refreshing a guest's company for this long after they last asked for it.
GUEST_INTEREST = timedelta(days=7)


def search_listed(db: Session, query: str) -> Sequence[ListedCompany]:
    # \m is Postgres for "start of a word", so "unity" won't match "Opportunity".
    name_matches = ListedCompany.name.regexp_match(rf"\m{re.escape(query)}", flags="i")
    ticker_matches = ListedCompany.ticker.istartswith(query, autoescape=True)
    best_first = case(
        (ListedCompany.ticker == query.upper(), 0),
        (ListedCompany.name.istartswith(query, autoescape=True), 1),
        (name_matches, 2),
        else_=3,
    )
    statement = (
        select(ListedCompany)
        .where(or_(ticker_matches, name_matches))
        .order_by(best_first, ListedCompany.name)
        .limit(SEARCH_LIMIT)
    )
    return db.scalars(statement).all()


def replace_listed(db: Session, companies: list[ListedCompanyData]) -> None:
    db.execute(delete(ListedCompany))
    db.execute(insert(ListedCompany), [company.model_dump() for company in companies])


def get_by_ticker(db: Session, ticker: str) -> Company | None:
    return db.scalar(select(Company).where(Company.ticker == ticker))


def list_due_for_refresh(db: Session, limit: int) -> Sequence[Company]:
    """Companies in use that have waited longest, starting with never fetched."""
    is_tracked = (
        select(TrackedCompany.user_id)
        .where(TrackedCompany.company_id == Company.id)
        .exists()
    )
    wanted_by_guest = Company.last_requested_at >= datetime.now(UTC) - GUEST_INTEREST
    statement = (
        select(Company)
        .where(or_(is_tracked, wanted_by_guest))
        .order_by(Company.last_fetched_at.asc().nulls_first(), Company.id)
        .limit(limit)
    )
    return db.scalars(statement).all()


def list_articles(db: Session, company_id: int) -> Sequence[Article]:
    statement = (
        select(Article)
        .where(Article.company_id == company_id)
        .order_by(Article.published_at.desc())
    )
    return db.scalars(statement).all()


def save_articles(db: Session, company_id: int, articles: list[FetchedArticle]) -> None:
    if not articles:
        return
    rows = [
        {"company_id": company_id, **article.model_dump(exclude={"description"})}
        for article in articles
    ]
    statement = (
        postgres_insert(Article)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_articles_company_url")
    )
    db.execute(statement)
