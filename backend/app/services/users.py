from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, User
from app.repositories import users as users_repository
from app.services import companies as companies_service


class UserNotFoundError(Exception):
    pass


def sign_in(db: Session, username: str) -> tuple[User, bool]:
    """Return the user, creating them on first sign-in, and whether they're new."""
    existing = users_repository.get_by_username(db, username)
    if existing:
        return existing, False

    user = User(username=username)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Another request created the same username first.
        db.rollback()
        return users_repository.get_by_username(db, username), False
    return user, True


def get_user(db: Session, username: str) -> User:
    user = users_repository.get_by_username(db, username.lower())
    if user is None:
        raise UserNotFoundError(username)
    return user


def track_company(db: Session, username: str, ticker: str) -> tuple[Company, bool]:
    """Return the company and whether this user newly started tracking it."""
    user = get_user(db, username)
    company, _ = companies_service.add_company(db, ticker)
    newly_tracked = users_repository.track(db, user.id, company.id)
    db.commit()
    return company, newly_tracked
