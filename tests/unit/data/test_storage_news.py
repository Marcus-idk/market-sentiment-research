"""
Tests news item storage operations and deduplication.
"""

import pytest
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from data.storage import (
    init_database, store_news_items, store_price_data,
    get_news_since, get_price_data_since, upsert_analysis_result,
    upsert_holdings, get_all_holdings, get_analysis_results,
    _normalize_url, _datetime_to_iso, _decimal_to_text,
    get_last_seen, set_last_seen, get_last_news_time, set_last_news_time,
    get_news_before, get_prices_before, commit_llm_batch, finalize_database
)

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
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
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
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
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM news_items")
            count = cursor.fetchone()[0]
            assert count == 0
