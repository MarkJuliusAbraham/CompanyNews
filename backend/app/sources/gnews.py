import logging
from datetime import datetime

import httpx

from app.config import settings
from app.schemas.news import FetchedArticle

API_URL = "https://gnews.io/api/v4/search"

# httpx logs each request URL at INFO level, and ours contains the API key.
logging.getLogger("httpx").setLevel(logging.WARNING)


class NewsSourceError(Exception):
    pass


def search_articles(
    query: str, since: datetime, limit: int = 10
) -> list[FetchedArticle]:
    if not settings.gnews_api_key:
        raise NewsSourceError("GNEWS_API_KEY is not set")

    params = {
        "q": query,
        "lang": "en",
        "max": limit,
        "from": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apikey": settings.gnews_api_key,
    }
    # "from None" keeps the request URL, which contains the key, out of the logs.
    try:
        response = httpx.get(API_URL, params=params, timeout=15)
    except httpx.HTTPError as error:
        raise NewsSourceError(type(error).__name__) from None
    if response.is_error:
        raise NewsSourceError(f"GNews returned {response.status_code}")

    try:
        return [to_article(item) for item in response.json().get("articles", [])]
    except (KeyError, TypeError, ValueError) as error:
        raise NewsSourceError("GNews returned unexpected data") from error


def to_article(item: dict) -> FetchedArticle:
    return FetchedArticle(
        title=item["title"],
        url=item["url"],
        source=item["source"]["name"],
        published_at=item["publishedAt"],
        description=item.get("description") or "",
    )
