"""
Tests cutoff/pagination logic for news and price data queries.
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

class TestCutoffQueries:
    """Test cutoff-based query operations for batch processing"""
    
    def test_get_news_before_cutoff_filtering(self, temp_db):
        """Test news retrieval with created_at cutoff filtering for LLM batch processing"""
        import time
        
        # Create news items with different created_at times
        # We need to insert them with delays to ensure different created_at_iso values
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # First item - oldest
        item1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/old",
            headline="Old News",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [item1])
        time.sleep(1)  # 1 second delay to ensure different created_at
        
        # Second item - middle
        item2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/middle",
            headline="Middle News",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [item2])
        
        # Record cutoff time right after second item
        cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay before third item
        
        # Third item - newest
        item3 = NewsItem(
            symbol="AAPL",
            url="https://example.com/new",
            headline="New News",
            source="Yahoo",
            published=base_time
        )
        store_news_items(temp_db, [item3])
        
        # Query news before cutoff (should get first 2 items)
        results = get_news_before(temp_db, cutoff)
        
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Verify ordering by created_at ASC, then symbol ASC
        assert results[0].headline == "Old News"
        assert results[1].headline == "Middle News"
        
        # Verify all expected fields are present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'url')
            assert hasattr(result, 'headline')
            assert hasattr(result, 'content')
            assert hasattr(result, 'published')
            assert hasattr(result, 'source')
    
    def test_get_news_before_boundary_conditions(self, temp_db):
        """Test get_news_before with boundary conditions using spaced items"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Store first news item
        item1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/item1",
            headline="First News",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [item1])
        time.sleep(1)  # 1 second delay
        
        # Record time between items
        between_cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay
        
        # Store second news item
        item2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/item2",
            headline="Second News",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [item2])
        
        # Test 1: Cutoff before all items (should get nothing)
        past_cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = get_news_before(temp_db, past_cutoff)
        assert len(results) == 0, f"Expected 0 results for past cutoff, got {len(results)}"
        
        # Test 2: Cutoff between items (should get first item only)
        results = get_news_before(temp_db, between_cutoff)
        assert len(results) == 1, f"Expected 1 result for between cutoff, got {len(results)}"
        assert results[0].headline == "First News"
        
        # Test 3: Cutoff well after all items (should get both)
        future_cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)
        results = get_news_before(temp_db, future_cutoff)
        assert len(results) == 2, f"Expected 2 results for future cutoff, got {len(results)}"
        
        # Test 4: Exact timestamp match with current time (should get both items)
        exact_cutoff = datetime.now(timezone.utc)
        results = get_news_before(temp_db, exact_cutoff)
        assert len(results) == 2, f"Expected 2 results for exact match, got {len(results)}"
    
    def test_get_prices_before_cutoff_filtering(self, temp_db):
        """Test price data retrieval with created_at cutoff filtering for LLM batch processing"""
        import time
        
        # Create price data with different created_at times
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # First price - oldest
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal('150.00'),
            session=Session.REG
        )
        store_price_data(temp_db, [price1])
        time.sleep(1)  # 1 second delay
        
        # Second price - middle
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time + timedelta(hours=1),
            price=Decimal('200.00'),
            session=Session.PRE
        )
        store_price_data(temp_db, [price2])
        
        # Record cutoff time right after second item
        cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay before third item
        
        # Third price - newest
        price3 = PriceData(
            symbol="AAPL",
            timestamp=base_time + timedelta(hours=2),
            price=Decimal('151.00'),
            session=Session.POST
        )
        store_price_data(temp_db, [price3])
        
        # Query prices before cutoff (should get first 2 items)
        results = get_prices_before(temp_db, cutoff)
        
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Verify ordering by created_at ASC, then symbol ASC
        assert results[0].price == Decimal('150.00')
        assert results[1].price == Decimal('200.00')
        
        # Verify all expected fields are present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'timestamp')
            assert hasattr(result, 'price')
            assert hasattr(result, 'volume')
            assert hasattr(result, 'session')
    
    def test_get_prices_before_boundary_conditions(self, temp_db):
        """Test get_prices_before with boundary conditions using spaced items"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Store first price data point
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal('150.00'),
            volume=1000000,
            session=Session.REG
        )
        store_price_data(temp_db, [price1])
        time.sleep(1)  # 1 second delay
        
        # Record time between items
        between_cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay
        
        # Store second price data point
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time + timedelta(hours=1),
            price=Decimal('200.00'),
            volume=2000000,
            session=Session.PRE
        )
        store_price_data(temp_db, [price2])
        
        # Test 1: Cutoff before all items (should get nothing)
        past_cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = get_prices_before(temp_db, past_cutoff)
        assert len(results) == 0, f"Expected 0 results for past cutoff, got {len(results)}"
        
        # Test 2: Cutoff between items (should get first item only)
        results = get_prices_before(temp_db, between_cutoff)
        assert len(results) == 1, f"Expected 1 result for between cutoff, got {len(results)}"
        assert results[0].price == Decimal('150.00')
        assert results[0].symbol == "AAPL"
        
        # Test 3: Cutoff well after all items (should get both)
        future_cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)
        results = get_prices_before(temp_db, future_cutoff)
        assert len(results) == 2, f"Expected 2 results for future cutoff, got {len(results)}"
        
        # Test 4: Exact timestamp match with current time (should get both items)
        exact_cutoff = datetime.now(timezone.utc)
        results = get_prices_before(temp_db, exact_cutoff)
        assert len(results) == 2, f"Expected 2 results for exact match, got {len(results)}"