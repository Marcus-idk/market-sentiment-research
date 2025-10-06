"""
Tests news item storage operations and deduplication.
"""

import pytest
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from data.storage import (
    init_database, store_news_items, store_news_labels, store_price_data,
    get_news_since, get_news_labels, get_price_data_since, upsert_analysis_result,
    upsert_holdings, get_all_holdings, get_analysis_results,
    get_last_seen, set_last_seen, get_last_news_time, set_last_news_time,
    get_news_before, get_prices_before, commit_llm_batch, finalize_database,
)
from data.storage.db_context import _cursor_context
from data.storage.storage_utils import _normalize_url, _datetime_to_iso, _decimal_to_text

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings, NewsLabel,
    Session, Stance, AnalysisType, NewsLabelType
)

class TestNewsItemStorage:
    """Test news item storage operations"""
    
    def test_store_news_deduplication_insert_or_ignore(self, temp_db):
        """Test news storage with URL normalization and deduplication"""
        # Create test news items with different URLs that normalize to same
        items = [
            NewsItem(
                symbol="AAPL",
                url="https://example.com/news/1?utm_source=google",
                headline="Apple News",
                source="Reuters",
                published=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
            ),
            NewsItem(
                symbol="AAPL", 
                url="https://example.com/news/1?ref=twitter",  # Same normalized URL
                headline="Apple News Updated",  # Different headline
                source="Reuters",
                published=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
            )
        ]
        
        # Store news items - second item should be ignored due to URL normalization
        store_news_items(temp_db, items)
        
        # Verify deduplication worked - only first item should remain
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("""
                SELECT COUNT(*), headline, url FROM news_items
                WHERE symbol = 'AAPL'
            """)
            count, headline, stored_url = cursor.fetchone()
            
            assert count == 1, f"Expected 1 record, got {count}"
            assert headline == "Apple News", "First record should be kept"
            assert stored_url == "https://example.com/news/1", "URL should be normalized"
    
    def test_store_news_empty_list_no_error(self, temp_db):
        """Test storing empty news list doesn't cause errors"""
        store_news_items(temp_db, [])  # Should not raise error
        
        # Verify no records stored
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_items")
            count = cursor.fetchone()[0]
            assert count == 0


class TestNewsLabelStorage:
    """Test news label storage operations."""

    def _seed_news(self, temp_db, symbol: str, url: str) -> NewsItem:
        news = NewsItem(
            symbol=symbol,
            url=url,
            headline=f"Headline for {symbol}",
            source="Test",
            published=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        )
        store_news_items(temp_db, [news])
        return news

    def test_store_and_get_news_labels(self, temp_db):
        """Storing labels persists them and get_news_labels returns NewsLabel models."""
        news = self._seed_news(temp_db, "AAPL", "https://example.com/news/primary")
        labeled_at = datetime(2024, 1, 15, 12, 5, tzinfo=timezone.utc)
        label = NewsLabel(symbol=news.symbol, url=news.url, label=NewsLabelType.COMPANY, created_at=labeled_at)

        store_news_labels(temp_db, [label])
        labels = get_news_labels(temp_db)

        assert len(labels) == 1
        stored = labels[0]
        assert stored.symbol == "AAPL"
        assert stored.url == "https://example.com/news/primary"
        assert stored.label is NewsLabelType.COMPANY
        assert stored.created_at == labeled_at

    def test_store_news_labels_upsert_updates_existing_label(self, temp_db):
        """Re-storing the same symbol/url updates the label value and timestamp."""
        news = self._seed_news(temp_db, "TSLA", "https://example.com/news/label")
        first_time = datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)
        second_time = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)

        first_label = NewsLabel(symbol=news.symbol, url=news.url, label=NewsLabelType.MARKET_WITH_MENTION, created_at=first_time)
        second_label = NewsLabel(symbol=news.symbol, url=news.url, label=NewsLabelType.PEOPLE, created_at=second_time)

        store_news_labels(temp_db, [first_label])
        store_news_labels(temp_db, [second_label])

        labels = get_news_labels(temp_db, symbol="TSLA")
        assert len(labels) == 1
        stored = labels[0]
        assert stored.label is NewsLabelType.PEOPLE
        assert stored.created_at == second_time

    def test_news_labels_cascade_on_news_deletion(self, temp_db):
        """Verify labels are automatically deleted when parent news item is deleted (CASCADE)."""
        # Create 2 news items
        news1 = self._seed_news(temp_db, "MSFT", "https://example.com/news/delete")
        news2 = self._seed_news(temp_db, "MSFT", "https://example.com/news/keep")

        # Add labels for both
        labels = [
            NewsLabel(symbol=news1.symbol, url=news1.url, label=NewsLabelType.COMPANY),
            NewsLabel(symbol=news2.symbol, url=news2.url, label=NewsLabelType.PEOPLE)
        ]
        store_news_labels(temp_db, labels)

        # Verify both labels exist
        all_labels = get_news_labels(temp_db)
        assert len(all_labels) == 2

        # Delete first news item (parent)
        normalized_url = _normalize_url(news1.url)
        with _cursor_context(temp_db) as cursor:
            cursor.execute("DELETE FROM news_items WHERE symbol = ? AND url = ?", ("MSFT", normalized_url))

        # Verify only the label for deleted news is gone (CASCADE worked)
        remaining = get_news_labels(temp_db, symbol="MSFT")
        assert len(remaining) == 1
        assert remaining[0].url == "https://example.com/news/keep"
        assert remaining[0].label is NewsLabelType.PEOPLE

    def test_get_news_labels_filters_by_symbol(self, temp_db):
        """Symbol filter returns only labels for the requested ticker."""
        self._seed_news(temp_db, "AAPL", "https://example.com/news/a")
        self._seed_news(temp_db, "TSLA", "https://example.com/news/b")

        labels = [
            NewsLabel(symbol="AAPL", url="https://example.com/news/a", label=NewsLabelType.COMPANY),
            NewsLabel(symbol="TSLA", url="https://example.com/news/b", label=NewsLabelType.PEOPLE)
        ]
        store_news_labels(temp_db, labels)

        aapl_labels = get_news_labels(temp_db, symbol="AAPL")
        assert len(aapl_labels) == 1
        assert aapl_labels[0].symbol == "AAPL"
        assert aapl_labels[0].label is NewsLabelType.COMPANY
