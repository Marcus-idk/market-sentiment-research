"""
Tests last_seen timestamp tracking for data providers.
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

class TestLastSeenState:
    """Test last_seen table key-value storage operations"""
    
    def test_basic_roundtrip_set_get(self, temp_db):
        """Test basic set/get functionality"""
        # Set a key-value pair using allowed key
        set_last_seen(temp_db, 'news_since_iso', '2024-01-15T10:30:00Z')
        
        # Retrieve it
        result = get_last_seen(temp_db, 'news_since_iso')
        assert result == '2024-01-15T10:30:00Z'
    
    def test_replace_existing_key(self, temp_db):
        """Test INSERT OR REPLACE behavior - overwriting existing keys"""
        # Set initial value
        set_last_seen(temp_db, 'llm_last_run_iso', '2024-01-15T09:00:00Z')
        assert get_last_seen(temp_db, 'llm_last_run_iso') == '2024-01-15T09:00:00Z'
        
        # Overwrite with new value
        set_last_seen(temp_db, 'llm_last_run_iso', '2024-01-15T10:00:00Z')
        
        # Should return the new value only
        result = get_last_seen(temp_db, 'llm_last_run_iso')
        assert result == '2024-01-15T10:00:00Z'
        
        # Verify only one record exists
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM last_seen WHERE key = 'llm_last_run_iso'")
            count = cursor.fetchone()[0]
            assert count == 1, "Should have exactly one record after replacement"
    
    def test_unknown_key_returns_none(self, temp_db):
        """Test that non-existent keys return None"""
        # Test with allowed key that hasn't been set
        result = get_last_seen(temp_db, 'news_since_iso')
        assert result is None
    
    def test_unicode_safety(self, temp_db):
        """Test unicode handling in values and key constraint enforcement"""
        # Test unicode value with allowed key
        unicode_value = 'résumé📈'
        set_last_seen(temp_db, 'news_since_iso', unicode_value)
        result = get_last_seen(temp_db, 'news_since_iso')
        assert result == unicode_value
        
        # Test both allowed keys work
        set_last_seen(temp_db, 'llm_last_run_iso', '2024-01-15T10:30:00Z')
        result = get_last_seen(temp_db, 'llm_last_run_iso')
        assert result == '2024-01-15T10:30:00Z'
    
    def test_key_constraint_enforcement(self, temp_db):
        """Test that CHECK constraint rejects invalid keys"""
        # Should raise constraint error for invalid key
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            set_last_seen(temp_db, 'invalid_key', 'some_value')

class TestLastNewsTime:
    """Test specialized last news time tracking functions"""
    
    def test_roundtrip_aware_timestamp(self, temp_db):
        """Test UTC-aware datetime roundtrip"""
        # Set a UTC-aware timestamp
        dt_aware = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        set_last_news_time(temp_db, dt_aware)
        
        # Retrieve it
        result = get_last_news_time(temp_db)
        
        # Should be equal when both are UTC-aware
        assert result == dt_aware
        assert result.tzinfo == timezone.utc
        
        # Check underlying storage format
        raw_value = get_last_seen(temp_db, 'news_since_iso')
        assert raw_value == "2024-01-15T10:30:45Z"
    
    def test_naive_timestamp_treated_as_utc(self, temp_db):
        """Test naive datetime is treated as UTC"""
        # Set naive timestamp
        dt_naive = datetime(2024, 1, 15, 10, 30, 45)
        set_last_news_time(temp_db, dt_naive)
        
        # Retrieve it - should be UTC-aware
        result = get_last_news_time(temp_db)
        expected = dt_naive.replace(tzinfo=timezone.utc)
        
        assert result == expected
        assert result.tzinfo == timezone.utc
        
        # Check underlying storage format
        raw_value = get_last_seen(temp_db, 'news_since_iso')
        assert raw_value == "2024-01-15T10:30:45Z"
    
    def test_overwrite_behavior(self, temp_db):
        """Test last write wins - no monotonic enforcement"""
        # Set older time first
        older_time = datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
        set_last_news_time(temp_db, older_time)
        assert get_last_news_time(temp_db) == older_time
        
        # Set newer time
        newer_time = datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)
        set_last_news_time(temp_db, newer_time)
        assert get_last_news_time(temp_db) == newer_time
        
        # Set even older time - should still work (last write wins)
        much_older_time = datetime(2024, 1, 14, 8, 0, tzinfo=timezone.utc)
        set_last_news_time(temp_db, much_older_time)
        assert get_last_news_time(temp_db) == much_older_time
    
    def test_missing_key_returns_none(self, temp_db):
        """Test None returned when news_since_iso key doesn't exist"""
        # Don't set anything
        result = get_last_news_time(temp_db)
        assert result is None
