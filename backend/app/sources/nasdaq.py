import csv
import re

import httpx

from app.schemas.news import ListedCompanyData

BASE_URL = "https://www.nasdaqtrader.com/dynamic/SymDir"
# Each file names its ticker column differently.
FILES = {"nasdaqlisted.txt": "Symbol", "otherlisted.txt": "ACT Symbol"}

NOT_A_COMPANY_SHARE = re.compile(
    r"\b(warrants?|units?|rights?|preferred|preference|perpetual|pfd|notes?"
    r"|debentures?|due \d{4}|funds?)\b",
    re.IGNORECASE,
)
SECURITY_WORDING = re.compile(
    r"\s+(?:New\s+)?(?:Class [A-Z]\s+)?"
    r"(?:Common Stock|Common Shares|Ordinary Shares|American Depositary Shares?"
    r"|Depositary Shares).*$",
    re.IGNORECASE,
)


class ListingSourceError(Exception):
    pass


def fetch_listed_companies() -> list[ListedCompanyData]:
    companies: dict[str, ListedCompanyData] = {}
    for filename, ticker_column in FILES.items():
        try:
            response = httpx.get(f"{BASE_URL}/{filename}", timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ListingSourceError(f"Could not download {filename}") from error
        for company in parse_listing(response.text, ticker_column):
            companies[company.ticker] = company
    return list(companies.values())


def parse_listing(text: str, ticker_column: str) -> list[ListedCompanyData]:
    companies = []
    for row in csv.DictReader(text.splitlines(), delimiter="|"):
        ticker = row[ticker_column]
        security = row["Security Name"]
        if (
            ticker.startswith("File Creation Time")
            or "$" in ticker
            or row["ETF"] == "Y"
            or row["Test Issue"] == "Y"
            or NOT_A_COMPANY_SHARE.search(security)
        ):
            continue
        companies.append(ListedCompanyData(ticker=ticker, name=clean_name(security)))
    return companies


def clean_name(security: str) -> str:
    name = security.split(" - ")[0]
    return SECURITY_WORDING.sub("", name).strip()
