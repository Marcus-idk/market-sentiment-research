"""
Tests news item storage operations and symbol link persistence.
"""

from data.models import NewsType
from data.storage import get_news_symbols, store_news_items
from data.storage.db_context import _cursor_context
from data.storage.storage_utils import _normalize_url
from tests.factories import make_news_entry


class TestNewsItemStorage:
    """Tests for storing NewsEntry objects."""

    def test_store_news_deduplication_insert_or_ignore(self, temp_db):
        """News entries sharing a normalized URL deduplicate into one article row."""
        entry_primary = make_news_entry(
            symbol="AAPL",
            url="https://example.com/news/1?utm_source=google",
            is_important=True,
            headline="Apple News",
        )
        entry_secondary = make_news_entry(
            symbol="MSFT",
            url="https://example.com/news/1?ref=twitter",
            is_important=False,
            headline="Apple News Updated",
        )

        store_news_items(temp_db, [entry_primary, entry_secondary])

        normalized_url = _normalize_url(entry_primary.url)
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_items")
            assert cursor.fetchone()[0] == 1

            cursor.execute(
                """
                SELECT url, headline, source, news_type
                FROM news_items
            """
            )
            row = cursor.fetchone()
            assert row["url"] == normalized_url
            assert row["headline"] == "Apple News"
            assert row["source"] == "UnitTest"
            assert row["news_type"] == NewsType.COMPANY_SPECIFIC.value

            cursor.execute(
                """
                SELECT url, symbol, is_important
                FROM news_symbols
                ORDER BY symbol ASC
            """
            )
            rows = cursor.fetchall()
            assert [(r["symbol"], r["is_important"]) for r in rows] == [
                ("AAPL", 1),
                ("MSFT", 0),
            ]

        # API facade returns NewsSymbol models with bool coercion
        symbols = get_news_symbols(temp_db)
        assert {(link.symbol, link.is_important) for link in symbols} == {
            ("AAPL", True),
            ("MSFT", False),
        }

    def test_store_news_empty_list_no_error(self, temp_db):
        """Storing an empty list is a no-op."""
        store_news_items(temp_db, [])

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_items")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM news_symbols")
            assert cursor.fetchone()[0] == 0


class TestNewsSymbolsStorage:
    """Tests for news_symbols persistence helpers."""

    def test_store_and_get_news_symbols(self, temp_db):
        """Persist entries with varying importance flags and round-trip via facade."""
        entries = [
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/news/a",
                is_important=True,
                headline="AAPL Headline",
            ),
            make_news_entry(
                symbol="MSFT",
                url="https://example.com/news/a",
                is_important=False,
                headline="MSFT Headline",
            ),
            make_news_entry(
                symbol="TSLA",
                url="https://example.com/news/b",
                is_important=None,
                headline="TSLA Headline",
                news_type=NewsType.MACRO,
            ),
        ]

        store_news_items(temp_db, entries)

        links = get_news_symbols(temp_db)
        assert len(links) == 3
        by_symbol = {link.symbol: link for link in links}
        assert by_symbol["AAPL"].is_important is True
        assert by_symbol["MSFT"].is_important is False
        assert by_symbol["TSLA"].is_important is None

    def test_get_news_symbols_filters_by_symbol(self, temp_db):
        """Filtering by symbol returns only matching links."""
        entries = [
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/news/a",
                is_important=True,
                headline="AAPL Headline",
            ),
            make_news_entry(
                symbol="TSLA",
                url="https://example.com/news/b",
                is_important=None,
                headline="TSLA Headline",
            ),
        ]

        store_news_items(temp_db, entries)

        tsla_links = get_news_symbols(temp_db, symbol="tsla")
        assert len(tsla_links) == 1
        assert tsla_links[0].symbol == "TSLA"
        assert tsla_links[0].url == _normalize_url("https://example.com/news/b")

    def test_news_symbols_cascade_on_news_deletion(self, temp_db):
        """Deleting a news_items row cascades to news_symbols."""
        article_url = "https://example.com/news/cascade?utm_campaign=test"
        entries = [
            make_news_entry(symbol="AAPL", url=article_url, is_important=True, headline="Shared"),
            make_news_entry(symbol="MSFT", url=article_url, is_important=None, headline="Shared"),
            make_news_entry(
                symbol="TSLA",
                url="https://example.com/news/keep",
                is_important=False,
                headline="Separate",
            ),
        ]

        store_news_items(temp_db, entries)

        with _cursor_context(temp_db) as cursor:
            cursor.execute(
                "DELETE FROM news_items WHERE url = ?",
                (_normalize_url(article_url),),
            )

        remaining = get_news_symbols(temp_db)
        assert {(link.symbol, link.url) for link in remaining} == {
            ("TSLA", _normalize_url("https://example.com/news/keep")),
        }

    def test_store_news_symbols_conflict_updates_is_important(self, temp_db):
        """Conflict updates mutate importance flags without duplicating rows."""
        url = "https://example.com/news/priority"
        symbol = "AAPL"
        initial_entry = make_news_entry(
            symbol=symbol,
            url=url,
            is_important=True,
            headline="Initial headline",
        )

        store_news_items(temp_db, [initial_entry])

        normalized_url = _normalize_url(url)
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_items WHERE url = ?", (normalized_url,))
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """
                SELECT symbol, is_important
                FROM news_symbols
                WHERE url = ?
            """,
                (normalized_url,),
            )
            row = cursor.fetchone()
            assert row["symbol"] == symbol
            assert row["is_important"] == 1

        updated_entry = make_news_entry(
            symbol=symbol,
            url="https://example.com/news/priority?utm_source=ignored",
            is_important=False,
            headline="Updated headline",
        )
        store_news_items(temp_db, [updated_entry])

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_items WHERE url = ?", (normalized_url,))
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """
                SELECT symbol, is_important
                FROM news_symbols
                WHERE url = ?
            """,
                (normalized_url,),
            )
            row = cursor.fetchone()
            assert row["symbol"] == symbol
            assert row["is_important"] == 0

        cleared_entry = make_news_entry(
            symbol=symbol,
            url=url,
            is_important=None,
            headline="Cleared importance",
        )
        store_news_items(temp_db, [cleared_entry])

        links = get_news_symbols(temp_db, symbol=symbol)
        assert len(links) == 1
        link = links[0]
        assert link.url == normalized_url
        assert link.is_important is None
