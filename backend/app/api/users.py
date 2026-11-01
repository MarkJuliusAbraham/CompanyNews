from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import users as users_repository
from app.schemas.news import CompanyCreate, CompanyResponse
from app.schemas.user import SignIn, UserResponse
from app.services import companies as companies_service
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])

Db = Annotated[Session, Depends(get_db)]


@router.post("/sign-in", status_code=status.HTTP_201_CREATED)
def sign_in(body: SignIn, response: Response, db: Db) -> UserResponse:
    user, created = users_service.sign_in(db, body.username)
    if not created:
        response.status_code = status.HTTP_200_OK
    return user


@router.get("/{username}/companies")
def list_tracked_companies(username: str, db: Db) -> list[CompanyResponse]:
    try:
        user = users_service.get_user(db, username)
    except users_service.UserNotFoundError as error:
        raise HTTPException(status_code=404, detail="User not found") from error
    return users_repository.list_tracked(db, user.id)


@router.post("/{username}/companies", status_code=status.HTTP_201_CREATED)
def track_company(
    username: str, body: CompanyCreate, response: Response, db: Db
) -> CompanyResponse:
    try:
        company, newly_tracked = users_service.track_company(db, username, body.ticker)
    except users_service.UserNotFoundError as error:
        raise HTTPException(status_code=404, detail="User not found") from error
    except companies_service.CompanyNotListedError as error:
        raise HTTPException(status_code=404, detail="Ticker not found") from error
    if not newly_tracked:
        response.status_code = status.HTTP_200_OK
    return company


@router.delete(
    "/{username}/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT
)
def untrack_company(username: str, company_id: int, db: Db) -> None:
    try:
        user = users_service.get_user(db, username)
    except users_service.UserNotFoundError as error:
        raise HTTPException(status_code=404, detail="User not found") from error
    users_repository.untrack(db, user.id, company_id)
    db.commit()
