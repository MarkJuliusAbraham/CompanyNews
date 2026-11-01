from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Company, TrackedCompany, User
from app.repositories import companies as companies_repository


def clear_real_interest(db: Session) -> None:
    """Hide real rows from these tests, which is undone when each test ends."""
    db.execute(update(Company).values(last_requested_at=None))
    db.query(TrackedCompany).delete()


def add_company(
    db: Session, ticker: str, fetched_at: datetime | None, user: User | None
) -> None:
    company = Company(
        ticker=ticker, name=ticker, search_name=ticker, last_fetched_at=fetched_at
    )
    db.add(company)
    db.flush()
    if user:
        db.add(TrackedCompany(user_id=user.id, company_id=company.id))
    db.flush()


def test_due_companies_are_tracked_only_and_oldest_first(db: Session) -> None:
    clear_real_interest(db)

    user = User(username="refresh_user")
    other = User(username="refresh_other")
    db.add_all([user, other])
    db.flush()

    add_company(db, "ZZNEW", None, user)
    add_company(db, "ZZOLD", datetime(2026, 1, 1, tzinfo=UTC), user)
    add_company(db, "ZZRECENT", datetime(2026, 6, 1, tzinfo=UTC), other)
    add_company(db, "ZZUNTRACKED", None, None)

    due = companies_repository.list_due_for_refresh(db, limit=10)
    assert [company.ticker for company in due] == ["ZZNEW", "ZZOLD", "ZZRECENT"]

    limited = companies_repository.list_due_for_refresh(db, limit=2)
    assert [company.ticker for company in limited] == ["ZZNEW", "ZZOLD"]


def test_company_tracked_by_two_users_appears_once(db: Session) -> None:
    clear_real_interest(db)
    first = User(username="refresh_a")
    second = User(username="refresh_b")
    db.add_all([first, second])
    db.flush()

    add_company(db, "ZZSHARED", None, first)
    company = db.query(Company).filter_by(ticker="ZZSHARED").one()
    db.add(TrackedCompany(user_id=second.id, company_id=company.id))
    db.flush()

    due = companies_repository.list_due_for_refresh(db, limit=10)
    assert [c.ticker for c in due] == ["ZZSHARED"]
