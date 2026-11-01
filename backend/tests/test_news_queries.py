from app.services.news_queries import build_query, mentions_company


def test_plain_company_searches_by_name() -> None:
    assert build_query("MSFT", "Microsoft") == '"Microsoft"'


def test_ambiguous_company_requires_the_ticker() -> None:
    assert build_query("AAPL", "Apple") == '"Apple" AND AAPL'


def test_aliases_are_added_with_or() -> None:
    assert build_query("GOOG", "Alphabet") == '"Alphabet" OR "Google"'


def test_ambiguous_company_with_aliases_groups_the_names() -> None:
    assert build_query("META", "Meta Platforms") == (
        '("Meta Platforms" OR "Facebook" OR "Instagram") AND META'
    )


def test_long_queries_drop_aliases_but_keep_the_name() -> None:
    long_name = "x" * 190

    assert build_query("U", long_name) == f'"{long_name}"'


def test_mentions_company_accepts_aliases_and_whole_words_only() -> None:
    assert mentions_company("Google ships an update", "GOOG", "Alphabet")
    assert mentions_company("unity engine update", "U", "Unity Software")
    assert not mentions_company("A call for unity in Congress", "U", "Unity Software")
    assert not mentions_company("Pineapple prices rise", "AAPL", "Apple")
