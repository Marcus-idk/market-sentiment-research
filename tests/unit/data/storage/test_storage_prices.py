"""
Tests price data storage operations and type handling.
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
    get_news_before, get_prices_before, commit_llm_batch, finalize_database,
    _cursor_context
)

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)

class TestPriceDataStorage:
    """Test price data storage operations"""
    
    def test_store_price_data_type_conversions(self, temp_db):
        """Test price data storage with Decimal and enum conversions"""
        # Create test price data
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
                price=Decimal('150.25'),
                volume=1000000,
                session=Session.REG
            )
        ]
        
        # Store price data
        store_price_data(temp_db, items)
        
        # Verify data stored with proper conversions
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("""
                SELECT symbol, timestamp_iso, price, volume, session
                FROM price_data WHERE symbol = 'AAPL'
            """)
            row = cursor.fetchone()
            
            assert row[0] == "AAPL"
            assert row[1] == "2024-01-15T09:30:00Z"  # ISO format
            assert row[2] == "150.25"  # Decimal as TEXT
            assert row[3] == 1000000  # Integer volume
            assert row[4] == "REG"  # Enum as string value
    
    def test_store_price_data_deduplication(self, temp_db):
        """Test price data deduplication on (symbol, timestamp) key"""
        # Create duplicate price data (same symbol, timestamp)
        timestamp = datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc)
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=timestamp,
                price=Decimal('150.00'),
                volume=1000000,
                session=Session.REG
            ),
            PriceData(
                symbol="AAPL",
                timestamp=timestamp,  # Same timestamp
                price=Decimal('151.00'),  # Different price
                volume=2000000,
                session=Session.PRE
            )
        ]
        
        # Store price data - second item should be ignored (same symbol+timestamp)
        store_price_data(temp_db, items)
        
        # Verify deduplication worked - first item wins with INSERT OR IGNORE
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("""
                SELECT COUNT(*), price FROM price_data
                WHERE symbol = 'AAPL' AND timestamp_iso = '2024-01-15T09:30:00Z'
            """)
            count, price = cursor.fetchone()
            
            assert count == 1, f"Expected 1 record, got {count}"
            assert price == "150.00", "First record should be kept"
