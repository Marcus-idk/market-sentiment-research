"""
Tests LLM batch operation storage and commit functionality.
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

class TestBatchOperations:
    """Test batch operations like commit_llm_batch and finalize_database"""
    
    def test_commit_llm_batch_atomic_transaction(self, temp_db):
        """Test commit_llm_batch performs atomic transaction with correct deletions"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Insert news items with different created_at times
        news1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="News 1",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [news1])
        time.sleep(1)
        
        news2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/news2",
            headline="News 2",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [news2])
        
        # Record cutoff between items 2 and 3
        cutoff = datetime.now(timezone.utc)
        time.sleep(1)
        
        news3 = NewsItem(
            symbol="GOOGL",
            url="https://example.com/news3",
            headline="News 3",
            source="Yahoo",
            published=base_time
        )
        store_news_items(temp_db, [news3])
        
        # Also insert price data with similar timing
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal('150.00'),
            session=Session.REG
        )
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time,
            price=Decimal('200.00'),
            session=Session.PRE
        )
        price3 = PriceData(
            symbol="GOOGL",
            timestamp=base_time,
            price=Decimal('100.00'),
            session=Session.POST
        )
        
        # Store price data (using existing created_at from news for simplicity)
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            # Insert prices with specific created_at times matching news items
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, session, created_at_iso)
                SELECT ?, ?, ?, ?, created_at_iso
                FROM news_items WHERE symbol = ?
            """, ("AAPL", _datetime_to_iso(base_time), str(price1.price), "REG", "AAPL"))
            
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, session, created_at_iso)
                SELECT ?, ?, ?, ?, created_at_iso
                FROM news_items WHERE symbol = ?
            """, ("TSLA", _datetime_to_iso(base_time), str(price2.price), "PRE", "TSLA"))
            
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, session, created_at_iso)
                SELECT ?, ?, ?, ?, created_at_iso
                FROM news_items WHERE symbol = ?
            """, ("GOOGL", _datetime_to_iso(base_time), str(price3.price), "POST", "GOOGL"))
            conn.commit()
        
        # Execute commit_llm_batch
        result = commit_llm_batch(temp_db, cutoff)
        
        # Verify return value
        assert result["news_deleted"] == 2, f"Expected 2 news deleted, got {result['news_deleted']}"
        assert result["prices_deleted"] == 2, f"Expected 2 prices deleted, got {result['prices_deleted']}"
        
        # Verify remaining data
        remaining_news = get_news_since(temp_db, datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert len(remaining_news) == 1, f"Expected 1 news item remaining, got {len(remaining_news)}"
        assert remaining_news[0].headline == "News 3"
        
        remaining_prices = get_price_data_since(temp_db, datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert len(remaining_prices) == 1, f"Expected 1 price remaining, got {len(remaining_prices)}"
        assert remaining_prices[0].symbol == "GOOGL"
        
        # Verify last_seen watermark was set
        assert get_last_seen(temp_db, 'llm_last_run_iso') == _datetime_to_iso(cutoff)
    
    def test_commit_llm_batch_empty_database(self, temp_db):
        """Test commit_llm_batch on empty database"""
        cutoff = datetime.now(timezone.utc)
        
        # Execute on empty database
        result = commit_llm_batch(temp_db, cutoff)
        
        # Should delete nothing
        assert result["news_deleted"] == 0
        assert result["prices_deleted"] == 0
        
        # Should still set the watermark
        assert get_last_seen(temp_db, 'llm_last_run_iso') == _datetime_to_iso(cutoff)
    
    def test_commit_llm_batch_boundary_conditions(self, temp_db):
        """Test commit_llm_batch with exact timestamp boundary"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Insert two items
        news1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="News 1",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [news1])
        time.sleep(1)
        
        # Get exact timestamp of second item
        news2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/news2",
            headline="News 2",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [news2])
        
        # Get the exact created_at of the second item
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at_iso FROM news_items WHERE symbol = 'TSLA'")
            exact_timestamp_iso = cursor.fetchone()[0]
        
        exact_cutoff = datetime.fromisoformat(exact_timestamp_iso.replace('Z', '+00:00'))
        
        # Commit with exact timestamp (should delete both due to <=)
        result = commit_llm_batch(temp_db, exact_cutoff)
        
        assert result["news_deleted"] == 2, f"Expected 2 deleted with <= boundary, got {result['news_deleted']}"
        
        # Verify all deleted
        remaining = get_news_since(temp_db, datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert len(remaining) == 0, f"Expected 0 items remaining, got {len(remaining)}"
    
    def test_commit_llm_batch_idempotency(self, temp_db):
        """Test commit_llm_batch can be called multiple times with same cutoff"""
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Insert test data
        news = NewsItem(
            symbol="AAPL",
            url="https://example.com/news",
            headline="Test News",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [news])
        
        cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)
        
        # First call should delete the item
        result1 = commit_llm_batch(temp_db, cutoff)
        assert result1["news_deleted"] == 1
        
        # Second call with same cutoff should delete nothing
        result2 = commit_llm_batch(temp_db, cutoff)
        assert result2["news_deleted"] == 0
        assert result2["prices_deleted"] == 0
        
        # Watermark should still be updated
        assert get_last_seen(temp_db, 'llm_last_run_iso') == _datetime_to_iso(cutoff)
