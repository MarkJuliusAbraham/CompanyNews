from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArticleData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    url: str
    source: str
    published_at: datetime


class FetchedArticle(ArticleData):
    """An article from the news source, before it's checked and saved."""

    description: str = ""


class ListedCompanyData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str


class CompanyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_to_upper=True)

    ticker: str = Field(min_length=1, max_length=16)


class GuestCompanies(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_to_upper=True)

    tickers: list[str] = Field(min_length=1, max_length=3)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    created_at: datetime
    last_fetched_at: datetime | None
