from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ListedCompany
from app.schemas.news import FetchedArticle
from app.sources import gnews


@pytest.fixture
def source_calls(monkeypatch: pytest.MonkeyPatch, db: Session) -> list[str]:
    db.add(ListedCompany(ticker="ZZZT", name="Zedtest Software Inc."))
    db.commit()
    calls: list[str] = []

    def search(query: str, since: datetime) -> list[FetchedArticle]:
        calls.append(query)
        return []

    monkeypatch.setattr(gnews, "search_articles", search)
    return calls


def test_sign_in_creates_once_and_ignores_case(client: TestClient) -> None:
    first = client.post("/users/sign-in", json={"username": " Mark_1 "})
    second = client.post("/users/sign-in", json={"username": "mark_1"})

    assert first.status_code == 201
    assert first.json()["username"] == "mark_1"
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.parametrize("username", ["a", "has space", "x" * 31])
def test_invalid_username_is_rejected(client: TestClient, username: str) -> None:
    response = client.post("/users/sign-in", json={"username": username})

    assert response.status_code == 422


def test_tracked_companies_are_per_user(
    client: TestClient, source_calls: list[str]
) -> None:
    client.post("/users/sign-in", json={"username": "ana"})
    client.post("/users/sign-in", json={"username": "ben"})

    response = client.post("/users/ana/companies", json={"ticker": "ZZZT"})

    assert response.status_code == 201
    assert [c["ticker"] for c in client.get("/users/ana/companies").json()] == ["ZZZT"]
    assert client.get("/users/ben/companies").json() == []


def test_second_user_shares_company_without_calling_source(
    client: TestClient, source_calls: list[str]
) -> None:
    client.post("/users/sign-in", json={"username": "ana"})
    client.post("/users/sign-in", json={"username": "ben"})

    first = client.post("/users/ana/companies", json={"ticker": "ZZZT"})
    second = client.post("/users/ben/companies", json={"ticker": "ZZZT"})
    repeat = client.post("/users/ben/companies", json={"ticker": "ZZZT"})

    assert second.status_code == 201
    assert repeat.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(source_calls) == 1


def test_unknown_user_returns_404(client: TestClient, source_calls: list[str]) -> None:
    assert client.get("/users/nobody/companies").status_code == 404
    response = client.post("/users/nobody/companies", json={"ticker": "ZZZT"})
    assert response.status_code == 404
    assert source_calls == []


def test_untrack_removes_only_that_users_link(
    client: TestClient, source_calls: list[str]
) -> None:
    client.post("/users/sign-in", json={"username": "ana"})
    client.post("/users/sign-in", json={"username": "ben"})
    company = client.post("/users/ana/companies", json={"ticker": "ZZZT"}).json()
    client.post("/users/ben/companies", json={"ticker": "ZZZT"})

    url = f"/users/ana/companies/{company['id']}"
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 204

    assert client.get("/users/ana/companies").json() == []
    assert len(client.get("/users/ben/companies").json()) == 1
    assert client.get(f"/companies/{company['id']}/articles").status_code == 200


def test_untrack_for_unknown_user_returns_404(client: TestClient) -> None:
    assert client.delete("/users/nobody/companies/1").status_code == 404
