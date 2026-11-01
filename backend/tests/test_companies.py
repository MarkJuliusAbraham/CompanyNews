from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.jobs.scheduler import seconds_until_next_run
from app.models import Company, ListedCompany, User
from app.schemas.news import FetchedArticle
from app.services import companies as companies_service
from app.services import news_queries
from app.sources import gnews, nasdaq

TICKER = "ZZZT"
TRACK_URL = "/users/testuser/companies"
ARTICLE = FetchedArticle(
    title="Zedtest Software ships an update",
    url="https://example.com/zedtest",
    source="Example News",
    published_at=datetime(2026, 10, 24, 17, 15, tzinfo=UTC),
)
UNRELATED = FetchedArticle(
    title="An unrelated story",
    url="https://example.com/other",
    source="Example News",
    published_at=datetime(2026, 10, 24, 17, 15, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def listed_company(db: Session) -> None:
    db.add(ListedCompany(ticker=TICKER, name="Zedtest Software Inc."))
    db.add(User(username="testuser"))
    db.commit()


@pytest.fixture
def source_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def search(query: str, since: datetime) -> list[FetchedArticle]:
        calls.append(query)
        return [ARTICLE, UNRELATED]

    monkeypatch.setattr(gnews, "search_articles", search)
    return calls


def test_search_finds_by_ticker_and_name(client: TestClient) -> None:
    by_ticker = client.get("/companies/search", params={"query": "zzzt"}).json()
    by_name = client.get("/companies/search", params={"query": "zedtest"}).json()

    expected = {"ticker": TICKER, "name": "Zedtest Software Inc."}
    assert by_ticker[0] == expected
    assert by_name[0] == expected


def test_search_matches_the_start_of_words_only(
    client: TestClient, db: Session
) -> None:
    db.add(ListedCompany(ticker="ZZZO", name="Zedopportune Trust"))
    db.add(ListedCompany(ticker="ZZZB", name="Big Portune Inc."))
    db.commit()

    found = client.get("/companies/search", params={"query": "portune"}).json()

    assert [company["ticker"] for company in found] == ["ZZZB"]


def test_new_company_is_saved_with_only_relevant_articles(
    client: TestClient, source_calls: list[str]
) -> None:
    response = client.post(TRACK_URL, json={"ticker": "zzzt"})

    assert response.status_code == 201
    assert response.json()["ticker"] == TICKER
    assert source_calls == ['"Zedtest Software"']

    articles = client.get(f"/companies/{response.json()['id']}/articles").json()
    assert [article["title"] for article in articles] == [ARTICLE.title]


def test_unlisted_ticker_is_rejected(
    client: TestClient, source_calls: list[str]
) -> None:
    response = client.post(TRACK_URL, json={"ticker": "NOPE9"})

    assert response.status_code == 404
    assert source_calls == []


def test_existing_company_does_not_call_the_source(
    client: TestClient, source_calls: list[str]
) -> None:
    first = client.post(TRACK_URL, json={"ticker": TICKER})
    second = client.post(TRACK_URL, json={"ticker": TICKER})

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(source_calls) == 1


def test_reading_does_not_call_the_source(
    client: TestClient, source_calls: list[str]
) -> None:
    company = client.post(TRACK_URL, json={"ticker": TICKER}).json()
    source_calls.clear()

    client.get(TRACK_URL)
    client.get(f"/companies/{company['id']}/articles")
    client.get("/companies/search", params={"query": "zed"})

    assert source_calls == []


def test_company_is_kept_when_first_fetch_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(query: str, since: datetime) -> list[FetchedArticle]:
        raise gnews.NewsSourceError

    monkeypatch.setattr(gnews, "search_articles", fail)

    response = client.post(TRACK_URL, json={"ticker": TICKER})

    assert response.status_code == 201
    assert response.json()["last_fetched_at"] is None


def test_refreshing_twice_does_not_duplicate_articles(
    client: TestClient, db: Session, source_calls: list[str]
) -> None:
    created = client.post(TRACK_URL, json={"ticker": TICKER}).json()

    companies_service.refresh_company(db, db.get(Company, created["id"]))

    assert len(client.get(f"/companies/{created['id']}/articles").json()) == 1


def test_articles_for_unknown_company_return_404(client: TestClient) -> None:
    assert client.get("/companies/999999/articles").status_code == 404


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Unity Software Inc.", "Unity Software"),
        ("United Airlines Holdings, Inc.", "United Airlines"),
        ("Microsoft Corporation", "Microsoft"),
    ],
)
def test_to_search_name(name: str, expected: str) -> None:
    assert companies_service.to_search_name(name) == expected


def test_is_relevant_matches_whole_words_only() -> None:
    match = Company(ticker=TICKER, name="", search_name="zedtest software")
    partial = Company(ticker=TICKER, name="", search_name="Zedtest Soft")

    assert companies_service.is_relevant(ARTICLE, match)
    assert not companies_service.is_relevant(ARTICLE, partial)


def test_parse_listing_keeps_only_company_shares() -> None:
    text = "\n".join(
        [
            "Symbol|Security Name|ETF|Test Issue",
            "U|Unity Software Inc. Common Stock|N|N",
            "MSFT|Microsoft Corporation - Common Stock|N|N",
            "BRK.B|Berkshire Hathaway Inc. New Common Stock|N|N",
            "AAAP|Pacer Barings CLO Market Flex ETF|Y|N",
            "ZZZ|Test Company Common Stock|N|Y",
            "ABCW|ABC Corp Warrants|N|N",
            "BAC$L|Bank of America Corporation Conv Pfd Ser L|N|N",
            "EOD|Allspring Global Dividend Opportunity Fund|N|N",
            "File Creation Time: 1030202618:01|||",
        ]
    )

    assert [
        (company.ticker, company.name)
        for company in nasdaq.parse_listing(text, "Symbol")
    ] == [
        ("U", "Unity Software Inc."),
        ("MSFT", "Microsoft Corporation"),
        ("BRK.B", "Berkshire Hathaway Inc."),
    ]


def test_next_run_is_later_today_or_tomorrow() -> None:
    before = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
    after = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)

    assert seconds_until_next_run(before) == 3600
    assert seconds_until_next_run(after) == 23 * 3600


@pytest.mark.parametrize(
    ("ticker", "first_days", "second_days"),
    [("ZAMB", 7, 1), ("ZPLN", 1, 1)],
)
def test_only_ambiguous_first_fetch_looks_back_further(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
    first_days: int,
    second_days: int,
) -> None:
    windows: list[int] = []

    def search(query: str, since: datetime) -> list[FetchedArticle]:
        windows.append(round((datetime.now(UTC) - since).total_seconds() / 86400))
        return []

    monkeypatch.setattr(gnews, "search_articles", search)
    monkeypatch.setattr(news_queries, "AMBIGUOUS_TICKERS", {"ZAMB"})
    company = Company(ticker=ticker, name="Zed", search_name="Zed")
    db.add(company)
    db.commit()

    companies_service.refresh_company(db, company)
    companies_service.refresh_company(db, company)

    assert windows == [first_days, second_days]
