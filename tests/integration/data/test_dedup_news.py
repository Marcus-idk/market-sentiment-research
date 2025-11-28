"""Validate URL normalization and cross-provider news deduplication."""

from datetime import UTC, datetime

from data.models import NewsEntry, NewsItem, NewsType
from data.storage import get_news_since, store_news_items


class TestNewsDeduplication:
    """News article deduplication across data sources"""

    def test_cross_provider_deduplication(self, temp_db):
        """URL normalization enables deduplication across provider variants."""
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        symbol = "AAPL"
        base_url = "https://news.example.com/apple-quarterly-results"

        # ========================================
        # CREATE DUPLICATE ARTICLES FROM DIFFERENT SOURCES
        # ========================================

        # Source 1: Finnhub with UTM parameters
        finnhub_article = NewsEntry(
            article=NewsItem(
                url=(
                    f"{base_url}?utm_source=finnhub&utm_campaign=api&utm_medium=financial&"
                    "utm_term=earnings"
                ),
                headline="Apple Reports Strong Q4 Earnings Beat Expectations",
                content=(
                    "Apple Inc. exceeded analyst expectations with quarterly earnings "
                    "showing robust iPhone sales and services growth."
                ),
                source="Finnhub API",
                published=test_timestamp,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            symbol=symbol,
            is_important=True,
        )

        # Source 2: Polygon with mixed tracking parameters (case-insensitive test)
        polygon_article = NewsEntry(
            article=NewsItem(
                url=(
                    f"{base_url}?UTM_SOURCE=polygon&ref=feed&fbclid=IwAR1234567890&"
                    "campaign=newsletter&utm_content=finance"
                ),
                headline="Apple Reports Strong Q4 Earnings Beat Expectations",  # Same headline
                content=(
                    "Apple Inc. exceeded analyst expectations with quarterly earnings "
                    "showing robust iPhone sales and services growth."
                ),
                source="Polygon",
                published=test_timestamp,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            symbol=symbol,
            is_important=False,
        )

        # Source 3: Google Analytics with additional tracking parameters
        google_article = NewsEntry(
            article=NewsItem(
                url=(
                    f"{base_url}?gclid=Cj0KCQjw-uH1BRCm&UTM_CAMPAIGN=finance&"
                    "utm_medium=cpc&fbclid=different123"
                ),
                headline="Apple Reports Strong Q4 Earnings Beat Expectations",
                content=(
                    "Apple Inc. exceeded analyst expectations with quarterly earnings "
                    "showing robust iPhone sales and services growth."
                ),
                source="Google News",
                published=test_timestamp,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            symbol=symbol,
            is_important=None,
        )

        # ========================================
        # STORE ARTICLES AND VERIFY DEDUPLICATION
        # ========================================

        # Store first article from Finnhub
        store_news_items(temp_db, [finnhub_article])

        # Verify first article is stored
        initial_results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        assert len(initial_results) == 1

        stored_article = initial_results[0]
        assert stored_article.symbol == symbol
        assert stored_article.source == "Finnhub API"

        # Verify URL normalization - tracking parameters should be removed
        expected_normalized_url = base_url  # Clean URL without any tracking parameters
        assert stored_article.url == expected_normalized_url

        # Store second article from Polygon (should be ignored due to duplicate normalized URL)
        store_news_items(temp_db, [polygon_article])

        # Store third article from Google (should also be ignored due to duplicate normalized URL)
        store_news_items(temp_db, [google_article])

        # Query all articles for the symbol
        final_results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))

        # CRITICAL ASSERTION: Only ONE record should exist despite storing three articles
        assert len(final_results) == 1, "cross-provider dedup must result in one article"

        final_article = final_results[0]

        # Verify the stored article maintains the original source (first one stored)
        assert final_article.symbol == symbol
        assert final_article.source == "Finnhub API"
        assert final_article.headline == "Apple Reports Strong Q4 Earnings Beat Expectations"

        # Verify the URL has ALL tracking parameters removed (case-insensitive)
        assert final_article.url == expected_normalized_url

        # Verify published timestamp is preserved correctly
        assert final_article.published == datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        # ========================================
        # VERIFY DIFFERENT SYMBOL IS NOT DEDUPLICATED
        # ========================================

        # Test with a different symbol to ensure deduplication is symbol-specific
        different_symbol = "TSLA"
        tesla_article = NewsEntry(
            article=NewsItem(
                url=f"{base_url}?utm_source=tesla_news&gclid=different_tracking",
                headline="Tesla News Using Same Base URL",
                content="This should be stored separately due to different symbol.",
                source="Tesla Source",
                published=test_timestamp,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            symbol=different_symbol,
            is_important=None,
        )

        store_news_items(temp_db, [tesla_article])

        # Query all articles - should now have 2 total (1 AAPL, 1 TSLA)
        all_results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        assert len(all_results) == 2

        # Verify both symbols are present
        symbols = {article.symbol for article in all_results}
        assert symbols == {"AAPL", "TSLA"}

        # Verify TSLA article has normalized URL
        tesla_result = next(article for article in all_results if article.symbol == "TSLA")
        assert tesla_result.url == expected_normalized_url
