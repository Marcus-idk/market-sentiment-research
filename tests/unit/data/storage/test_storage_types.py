"""
Tests type conversion helper functions (_datetime_to_iso, _decimal_to_text).
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
    get_last_seen, set_last_seen, get_last_news_time, set_last_news_time,
    get_news_before, get_prices_before, commit_llm_batch, finalize_database
)
from data.storage.storage_utils import _normalize_url, _datetime_to_iso, _decimal_to_text

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)

class TestTypeConversions:
    """Test type conversion helper functions"""
    
    def test_datetime_to_iso_format_utc_aware(self):
        """Test UTC-aware datetime conversion to ISO format"""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45Z"
        assert result == expected
    
    def test_datetime_to_iso_format_naive(self):
        """Test naive datetime conversion to ISO format (treated as UTC)"""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45Z"  # Z suffix added (naive treated as UTC)
        assert result == expected
    
    def test_datetime_to_iso_strips_microseconds(self):
        """Test microseconds are stripped from datetime"""
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45Z"  # Microseconds stripped
        assert result == expected
    
    def test_decimal_to_text_precision_preservation(self):
        """Test Decimal to TEXT preserves exact precision"""
        test_cases = [
            (Decimal('123.45'), '123.45'),
            (Decimal('0.000001'), '0.000001'),
            (Decimal('999999.999999'), '999999.999999'),
            (Decimal('10.0'), '10.0'),  # Trailing zero preserved
            (Decimal('0'), '0'),
        ]
        
        for decimal_val, expected in test_cases:
            result = _decimal_to_text(decimal_val)
            assert result == expected, f"Failed for {decimal_val}: expected {expected}, got {result}"
