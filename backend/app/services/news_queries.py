import re

MAX_QUERY_LENGTH = 200  # GNews's limit

# Companies whose names are everyday words, so the ticker must appear too.
AMBIGUOUS_TICKERS = {
    "AAPL",
    "ALL",
    "AMZN",
    "CAT",
    "COST",
    "GAP",
    "META",
    "ON",
    "SHOP",
    "SNOW",
    "SPOT",
    "TGT",
    "TWLO",
}

# Other names a company's news goes by.
ALIASES = {
    "GOOG": ["Google"],
    "GOOGL": ["Google"],
    "META": ["Facebook", "Instagram"],
    "U": ["Unity Technologies", "Unity engine", "Unity 3D"],
}


def names_for(ticker: str, search_name: str) -> list[str]:
    return [search_name, *ALIASES.get(ticker, [])]


def build_query(ticker: str, search_name: str) -> str:
    names = [name.replace('"', "") for name in names_for(ticker, search_name)]
    requires_ticker = ticker in AMBIGUOUS_TICKERS

    # Drop aliases from the end, since the first name is the one that must stay.
    while True:
        query = " OR ".join(f'"{name}"' for name in names)
        if requires_ticker:
            query = (
                f"({query}) AND {ticker}" if len(names) > 1 else f"{query} AND {ticker}"
            )
        if len(query) <= MAX_QUERY_LENGTH or len(names) == 1:
            return query
        names.pop()


def mentions_company(text: str, ticker: str, search_name: str) -> bool:
    pattern = "|".join(re.escape(name) for name in names_for(ticker, search_name))
    return re.search(rf"\b(?:{pattern})\b", text, re.IGNORECASE) is not None


def is_ambiguous(ticker: str) -> bool:
    return ticker in AMBIGUOUS_TICKERS
