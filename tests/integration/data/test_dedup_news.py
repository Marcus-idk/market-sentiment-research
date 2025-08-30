"""
News deduplication tests.
Tests URL normalization and cross-provider deduplication functionality
to ensure duplicate articles from different sources are properly handled.
"""

import pytest
from datetime import datetime, timezone

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration]

from data.storage import store_news_items, get_news_since
from data.models import NewsItem


class TestNewsDeduplication:
    """Test news article deduplication across different data sources"""
    
    def test_cross_provider_deduplication(self, temp_db):
        """
        Test that URL normalization enables cross-provider deduplication.
        
        This test validates that different data sources providing the same article
        with different tracking parameters are properly deduplicated through:
        1. URL normalization removing tracking parameters
        2. INSERT OR IGNORE constraint on (symbol, url) primary key
        3. Only one record stored regardless of source
        """
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        symbol = "AAPL"
        base_url = "https://news.example.com/apple-quarterly-results"
        
        # Create the same news article from different data sources with various tracking parameters
        # Source 1: Finnhub with UTM parameters
        finnhub_article = NewsItem(
            symbol=symbol,
            url=f"{base_url}?utm_source=finnhub&utm_campaign=api&utm_medium=financial&utm_term=earnings",
            headline="Apple Reports Strong Q4 Earnings Beat Expectations",
            content="Apple Inc. exceeded analyst expectations with quarterly earnings showing robust iPhone sales and services growth.",
            source="Finnhub API",
            published=test_timestamp
        )
        
        # Source 2: RSS Feed with mixed tracking parameters (case-insensitive test)
        rss_article = NewsItem(
            symbol=symbol,
            url=f"{base_url}?UTM_SOURCE=rss&ref=feed&fbclid=IwAR1234567890&campaign=newsletter&utm_content=finance",
            headline="Apple Reports Strong Q4 Earnings Beat Expectations",  # Same headline
            content="Apple Inc. exceeded analyst expectations with quarterly earnings showing robust iPhone sales and services growth.",  # Same content
            source="RSS Feed",
            published=test_timestamp
        )
        
        # Source 3: Google Analytics with additional tracking parameters
        google_article = NewsItem(
            symbol=symbol,
            url=f"{base_url}?gclid=Cj0KCQjw-uH1BRCm&UTM_CAMPAIGN=finance&utm_medium=cpc&fbclid=different123",
            headline="Apple Reports Strong Q4 Earnings Beat Expectations",  # Same headline  
            content="Apple Inc. exceeded analyst expectations with quarterly earnings showing robust iPhone sales and services growth.",  # Same content
            source="Google News",
            published=test_timestamp
        )
        
        # Store first article from Finnhub
        store_news_items(temp_db, [finnhub_article])
        
        # Verify first article is stored
        initial_results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(initial_results) == 1, f"Expected 1 article after first insert, got {len(initial_results)}"
        
        stored_article = initial_results[0]
        assert stored_article['symbol'] == symbol
        assert stored_article['source'] == "Finnhub API"
        
        # Verify URL normalization - tracking parameters should be removed
        expected_normalized_url = base_url  # Clean URL without any tracking parameters
        assert stored_article['url'] == expected_normalized_url, f"Expected normalized URL '{expected_normalized_url}', got '{stored_article['url']}'"
        
        # Store second article from RSS (should be ignored due to duplicate normalized URL)
        store_news_items(temp_db, [rss_article])
        
        # Store third article from Google (should also be ignored due to duplicate normalized URL)
        store_news_items(temp_db, [google_article])
        
        # Query all articles for the symbol
        final_results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        
        # CRITICAL ASSERTION: Only ONE record should exist despite storing three articles
        assert len(final_results) == 1, f"Expected exactly 1 deduplicated article, got {len(final_results)} articles. Deduplication failed!"
        
        final_article = final_results[0]
        
        # Verify the stored article maintains the original source (first one stored)
        assert final_article['symbol'] == symbol
        assert final_article['source'] == "Finnhub API", "The first stored article's source should be preserved"
        assert final_article['headline'] == "Apple Reports Strong Q4 Earnings Beat Expectations"
        
        # Verify the URL has ALL tracking parameters removed (case-insensitive)
        assert final_article['url'] == expected_normalized_url, f"Final stored URL should be normalized: '{expected_normalized_url}', got '{final_article['url']}'"
        
        # Verify published timestamp is preserved correctly  
        assert final_article['published_iso'] == "2024-01-15T12:00:00Z"
        
        # Test with a different symbol to ensure deduplication is symbol-specific
        different_symbol = "TSLA"
        tesla_article = NewsItem(
            symbol=different_symbol,
            url=f"{base_url}?utm_source=tesla_news&gclid=different_tracking",  # Same base URL, different symbol
            headline="Tesla News Using Same Base URL",
            content="This should be stored separately due to different symbol.",
            source="Tesla Source",
            published=test_timestamp
        )
        
        store_news_items(temp_db, [tesla_article])
        
        # Query all articles - should now have 2 total (1 AAPL, 1 TSLA)
        all_results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(all_results) == 2, f"Expected 2 articles (1 per symbol), got {len(all_results)}"
        
        # Verify both symbols are present
        symbols = {article['symbol'] for article in all_results}
        assert symbols == {"AAPL", "TSLA"}, f"Expected symbols AAPL and TSLA, got {symbols}"
        
        # Verify TSLA article has normalized URL
        tesla_result = next(article for article in all_results if article['symbol'] == "TSLA")
        assert tesla_result['url'] == expected_normalized_url, f"TSLA article should also have normalized URL: '{expected_normalized_url}', got '{tesla_result['url']}'"
