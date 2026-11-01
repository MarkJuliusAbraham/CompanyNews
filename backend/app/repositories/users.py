from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Company, TrackedCompany, User


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def list_tracked(db: Session, user_id: int) -> Sequence[Company]:
    statement = (
        select(Company)
        .join(TrackedCompany, TrackedCompany.company_id == Company.id)
        .where(TrackedCompany.user_id == user_id)
        .order_by(Company.name)
    )
    return db.scalars(statement).all()


def track(db: Session, user_id: int, company_id: int) -> bool:
    """Return whether this added a new link, rather than one already there."""
    statement = (
        insert(TrackedCompany)
        .values(user_id=user_id, company_id=company_id)
        .on_conflict_do_nothing()
        .returning(TrackedCompany.user_id)
    )
    return db.scalar(statement) is not None


def untrack(db: Session, user_id: int, company_id: int) -> None:
    db.execute(
        delete(TrackedCompany).where(
            TrackedCompany.user_id == user_id,
            TrackedCompany.company_id == company_id,
        )
    )
