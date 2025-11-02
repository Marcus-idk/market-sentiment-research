"""
Tests LLM batch operation storage and commit functionality.
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from data.models import Session
from data.storage import (
    commit_llm_batch,
    get_last_seen,
    get_news_since,
    get_news_symbols,
    get_price_data_since,
    store_news_items,
    store_price_data,
)
from data.storage.db_context import _cursor_context
from data.storage.storage_utils import _datetime_to_iso, _iso_to_datetime, _normalize_url
from tests.factories import make_news_entry, make_price_data


def _get_created_at(temp_db: str, url: str) -> datetime:
    normalized_url = _normalize_url(url)
    with _cursor_context(temp_db, commit=False) as cursor:
        cursor.execute("SELECT created_at_iso FROM news_items WHERE url = ?", (normalized_url,))
        row = cursor.fetchone()
        assert row is not None
        return _iso_to_datetime(row[0])


class TestBatchOperations:
    """Tests for commit_llm_batch behavior."""

    def test_commit_llm_batch_atomic_transaction(self, temp_db):
        """commit_llm_batch prunes rows <= cutoff and returns counts."""
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        entry1 = make_news_entry(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="News 1",
            is_important=True,
            source="Source",
            published=base_time,
        )
        store_news_items(temp_db, [entry1])
        store_price_data(
            temp_db,
            [
                make_price_data(
                    symbol="AAPL",
                    timestamp=base_time,
                    price=Decimal("150.00"),
                    session=Session.REG,
                )
            ],
        )
        time.sleep(1)

        entry2 = make_news_entry(
            symbol="TSLA",
            url="https://example.com/news2",
            headline="News 2",
            is_important=False,
            source="Source",
            published=base_time,
        )
        store_news_items(temp_db, [entry2])
        store_price_data(
            temp_db,
            [
                make_price_data(
                    symbol="TSLA",
                    timestamp=base_time,
                    price=Decimal("200.00"),
                    session=Session.PRE,
                )
            ],
        )

        cutoff = datetime.now(UTC)
        time.sleep(1)

        entry3 = make_news_entry(
            symbol="GOOGL",
            url="https://example.com/news3",
            headline="News 3",
            is_important=None,
            source="Source",
            published=base_time,
        )
        store_news_items(temp_db, [entry3])
        store_price_data(
            temp_db,
            [
                make_price_data(
                    symbol="GOOGL",
                    timestamp=base_time,
                    price=Decimal("100.00"),
                    session=Session.POST,
                )
            ],
        )

        result = commit_llm_batch(temp_db, cutoff)

        assert result["symbols_deleted"] == 2
        assert result["news_deleted"] == 2
        assert result["prices_deleted"] == 2

        remaining_news = get_news_since(temp_db, datetime(2020, 1, 1, tzinfo=UTC))
        assert len(remaining_news) == 1
        remaining_entry = remaining_news[0]
        assert remaining_entry.symbol == "GOOGL"
        assert remaining_entry.headline == "News 3"

        remaining_symbols = get_news_symbols(temp_db)
        assert [(link.symbol, link.is_important) for link in remaining_symbols] == [("GOOGL", None)]

        remaining_prices = get_price_data_since(temp_db, datetime(2020, 1, 1, tzinfo=UTC))
        assert len(remaining_prices) == 1
        assert remaining_prices[0].symbol == "GOOGL"

        assert get_last_seen(temp_db, "llm_last_run_iso") == _datetime_to_iso(cutoff)

    def test_commit_llm_batch_empty_database(self, temp_db):
        """Empty database should still set watermark and delete nothing."""
        cutoff = datetime.now(UTC)

        result = commit_llm_batch(temp_db, cutoff)

        assert result == {"symbols_deleted": 0, "news_deleted": 0, "prices_deleted": 0}
        assert get_last_seen(temp_db, "llm_last_run_iso") == _datetime_to_iso(cutoff)

    def test_commit_llm_batch_boundary_conditions(self, temp_db):
        """Rows with created_at <= cutoff are deleted (inclusive boundary)."""
        entry1 = make_news_entry(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="News 1",
            is_important=True,
            source="Source",
        )
        store_news_items(temp_db, [entry1])
        time.sleep(1)

        entry2 = make_news_entry(
            symbol="TSLA",
            url="https://example.com/news2",
            headline="News 2",
            is_important=False,
            source="Source",
        )
        store_news_items(temp_db, [entry2])

        exact_cutoff = _get_created_at(temp_db, entry2.url)

        result = commit_llm_batch(temp_db, exact_cutoff)

        assert result["symbols_deleted"] == 2
        assert result["news_deleted"] == 2
        assert get_news_since(temp_db, datetime(2020, 1, 1, tzinfo=UTC)) == []
        assert get_news_symbols(temp_db) == []

    def test_commit_llm_batch_idempotency(self, temp_db):
        """Repeated calls with same cutoff delete only once."""
        entry = make_news_entry(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="Test News",
            is_important=True,
            source="Source",
        )
        store_news_items(temp_db, [entry])

        cutoff = datetime.now(UTC) + timedelta(seconds=1)

        result1 = commit_llm_batch(temp_db, cutoff)
        assert result1["symbols_deleted"] == 1
        assert result1["news_deleted"] == 1

        result2 = commit_llm_batch(temp_db, cutoff)
        assert result2 == {"symbols_deleted": 0, "news_deleted": 0, "prices_deleted": 0}
        assert get_last_seen(temp_db, "llm_last_run_iso") == _datetime_to_iso(cutoff)
