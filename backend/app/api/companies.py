from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company
from app.repositories import companies as companies_repository
from app.schemas.news import (
    ArticleData,
    CompanyResponse,
    GuestCompanies,
    ListedCompanyData,
)
from app.services import companies as companies_service

router = APIRouter(prefix="/companies", tags=["companies"])

Db = Annotated[Session, Depends(get_db)]


@router.get("/search")
def search_companies(
    query: Annotated[str, Query(min_length=1, max_length=100)], db: Db
) -> list[ListedCompanyData]:
    return companies_repository.search_listed(db, query.strip())


@router.post("/guest")
def get_guest_companies(body: GuestCompanies, db: Db) -> list[CompanyResponse]:
    return companies_service.get_guest_companies(db, body.tickers)


@router.get("/{company_id}/articles")
def list_articles(company_id: int, db: Db) -> list[ArticleData]:
    if db.get(Company, company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return companies_repository.list_articles(db, company_id)
