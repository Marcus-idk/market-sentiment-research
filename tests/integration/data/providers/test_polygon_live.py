"""Live integration tests for Polygon providers using the real API."""

from datetime import UTC, datetime, timedelta

import pytest

from data.providers.polygon import PolygonNewsProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_news_fetch(polygon_settings):
    """Test fetching real news data from Polygon API."""
    provider = PolygonNewsProvider(polygon_settings, ["AAPL"])

    assert await provider.validate_connection() is True

    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)

    # Basic validation if we get any results
    if results:
        article = results[0]
        assert article.symbol == "AAPL"
        assert article.headline and len(article.headline) > 0
        assert article.url and article.url.startswith("http")
        assert article.published.tzinfo == UTC
        assert article.source is not None
    else:
        pass


async def test_live_multiple_symbols(polygon_settings):
    """Test fetching news for multiple symbols."""
    # Test with multiple popular symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]
    provider = PolygonNewsProvider(polygon_settings, symbols)

    # Fetch news
    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)
    fetched_symbols = {r.symbol for r in results}

    # At least one symbol should have data (news may be sparse)
    assert len(fetched_symbols) >= 1

    # All fetched news entries should be valid
    for article in results:
        assert article.symbol in symbols
        assert article.headline and article.url.startswith("http")


async def test_live_error_handling(polygon_settings):
    """Test error handling with invalid symbol."""
    # Test with invalid symbol
    provider = PolygonNewsProvider(polygon_settings, ["INVALID_SYMBOL_XYZ123"])

    # Should not raise, just return empty or skip invalid
    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert len(results) == 0 or all(
        article.headline and article.url.startswith("http") for article in results
    )
