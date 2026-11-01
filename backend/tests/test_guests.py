from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Company, ListedCompany
from app.repositories import companies as companies_repository
from app.schemas.news import FetchedArticle
from app.sources import gnews

URL = "/companies/guest"


@pytest.fixture
def source_calls(monkeypatch: pytest.MonkeyPatch, db: Session) -> list[str]:
    db.add(ListedCompany(ticker="ZZZG", name="Zedguest Software Inc."))
    db.commit()
    calls: list[str] = []

    def search(query: str, since: datetime) -> list[FetchedArticle]:
        calls.append(query)
        return []

    monkeypatch.setattr(gnews, "search_articles", search)
    return calls


def test_guest_company_is_added_once(
    client: TestClient, source_calls: list[str]
) -> None:
    first = client.post(URL, json={"tickers": ["zzzg"]})
    second = client.post(URL, json={"tickers": ["ZZZG"]})

    assert [company["ticker"] for company in first.json()] == ["ZZZG"]
    assert second.json()[0]["id"] == first.json()[0]["id"]
    assert len(source_calls) == 1


def test_guest_cannot_request_more_than_three(client: TestClient) -> None:
    response = client.post(URL, json={"tickers": ["A", "B", "C", "D"]})

    assert response.status_code == 422


def test_unlisted_guest_ticker_is_left_out(
    client: TestClient, source_calls: list[str]
) -> None:
    response = client.post(URL, json={"tickers": ["NOPE9", "ZZZG"]})

    assert [company["ticker"] for company in response.json()] == ["ZZZG"]


def test_only_recent_guest_companies_are_due(
    client: TestClient, db: Session, source_calls: list[str]
) -> None:
    db.execute(update(Company).values(last_requested_at=None))
    client.post(URL, json={"tickers": ["ZZZG"]})

    def due() -> list[str]:
        companies = companies_repository.list_due_for_refresh(db, limit=500)
        return [company.ticker for company in companies]

    assert "ZZZG" in due()

    long_ago = datetime.now(UTC) - timedelta(days=8)
    db.execute(update(Company).values(last_requested_at=long_ago))
    assert "ZZZG" not in due()
