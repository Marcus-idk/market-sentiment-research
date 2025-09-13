"""
Tests URL normalization and deduplication logic for news items.
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

class TestURLNormalization:
    """Test URL normalization for cross-provider deduplication"""
    
    def test_normalize_url_strips_tracking_parameters(self):
        """Test removal of common tracking parameters (case-insensitive)"""
        test_cases = [
            # UTM parameters
            ("https://example.com?utm_source=google&utm_medium=cpc", 
             "https://example.com"),
            ("https://example.com?utm_campaign=test&utm_term=keyword", 
             "https://example.com"),
            ("https://example.com?utm_content=banner&other=keep", 
             "https://example.com?other=keep"),
             
            # Other tracking parameters
            ("https://example.com?ref=twitter&fbclid=abc123", 
             "https://example.com"),
            ("https://example.com?gclid=xyz789&msclkid=def456", 
             "https://example.com"),
            ("https://example.com?source=newsletter&campaign=promo", 
             "https://example.com?source=newsletter"),
             
            # Case insensitive removal
            ("https://example.com?UTM_Source=google&CAMPAIGN=test", 
             "https://example.com"),
            ("https://example.com?REF=twitter&Source=email", 
             "https://example.com?Source=email"),
        ]
        
        for original, expected in test_cases:
            result = _normalize_url(original)
            assert result == expected, f"Failed for {original}: expected {expected}, got {result}"
    
    def test_normalize_url_preserves_essential_parameters(self):
        """Test non-tracking parameters are preserved"""
        test_cases = [
            ("https://example.com?id=123&page=2", 
             "https://example.com?id=123&page=2"),
            ("https://example.com?q=search&sort=date", 
             "https://example.com?q=search&sort=date"),
            ("https://example.com?article=news&category=tech", 
             "https://example.com?article=news&category=tech"),
        ]
        
        for original, expected in test_cases:
            result = _normalize_url(original)
            assert result == expected, f"Failed for {original}: expected {expected}, got {result}"
    
    def test_normalize_url_canonical_ordering(self):
        """Test consistent parameter ordering"""
        # Parameters should be sorted for consistent results
        original = "https://example.com?z=last&a=first&m=middle"
        result = _normalize_url(original)
        
        # Should be in alphabetical order
        assert result == "https://example.com?a=first&m=middle&z=last"
    
    def test_normalize_url_mixed_tracking_and_essential(self):
        """Test mixed tracking and essential parameters"""
        original = "https://example.com?id=123&utm_source=google&page=2&ref=twitter&sort=date"
        expected = "https://example.com?id=123&page=2&sort=date"
        result = _normalize_url(original)
        assert result == expected
    
    def test_normalize_url_lowercases_hostname(self):
        """Test hostname is lowercased for consistent deduplication"""
        assert _normalize_url("HTTP://Example.COM/p?a=1&utm_source=x") == "http://example.com/p?a=1"
        
        # Additional test cases
        test_cases = [
            ("HTTPS://EXAMPLE.COM/news", "https://example.com/news"),
            ("Http://Example.Com/article", "http://example.com/article"),
            ("https://NEWS.Example.COM/page", "https://news.example.com/page"),
            ("HTTP://API.FINNHUB.IO/v1/news", "http://api.finnhub.io/v1/news"),
        ]
        
        for original, expected in test_cases:
            result = _normalize_url(original)
            assert result == expected, f"Failed for {original}: expected {expected}, got {result}"
