"""Live integration tests for Finnhub providers using the real API."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from data.providers.finnhub import FinnhubNewsProvider, FinnhubPriceProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_quote_fetch(finnhub_settings):
    """Test fetching real quote data from Finnhub API"""
    # Test with SPY (always available during market hours)
    provider = FinnhubPriceProvider(finnhub_settings, ["SPY"])

    # Validate connection first
    assert await provider.validate_connection() is True

    # Fetch quote
    results = await provider.fetch_incremental()

    # Basic validation
    assert len(results) >= 1

    spy_quote = results[0]
    assert spy_quote.symbol == "SPY"
    assert spy_quote.price > 0
    assert isinstance(spy_quote.price, Decimal)
    assert spy_quote.timestamp is not None
    assert spy_quote.timestamp.tzinfo == UTC
    assert spy_quote.session is not None


async def test_live_news_fetch(finnhub_settings):
    """Test fetching real news data from Finnhub API"""
    # Test with AAPL (usually has news)
    provider = FinnhubNewsProvider(finnhub_settings, ["AAPL"])

    # Validate connection first
    assert await provider.validate_connection() is True

    # Fetch news from last 3 days
    since = datetime.now(UTC) - timedelta(days=3)
    results = await provider.fetch_incremental(since=since)

    # May not always have news, so just validate structure if we get any
    if results:
        # Check first article
        article = results[0]
        assert article.symbol == "AAPL"
        assert article.headline and len(article.headline) > 0
        assert article.url and article.url.startswith("http")
        assert article.published is not None
        assert article.published.tzinfo == UTC
        assert article.source is not None
    else:
        pass


async def test_live_multiple_symbols(finnhub_settings):
    """Test fetching data for multiple symbols"""
    # Test with multiple popular symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]
    provider = FinnhubPriceProvider(finnhub_settings, symbols)

    # Fetch quotes
    results = await provider.fetch_incremental()

    # Should get quotes for all symbols (during market hours)
    fetched_symbols = {r.symbol for r in results}

    # At least one symbol should have data
    assert len(fetched_symbols) >= 1

    # All fetched quotes should be valid
    for quote in results:
        assert quote.symbol in symbols
        assert quote.price > 0
        assert isinstance(quote.price, Decimal)


async def test_live_error_handling(finnhub_settings):
    """Test error handling with invalid symbol via price provider.

    Notes:
    - Finnhub has both price and news providers; we exercise price here.
    - Polygon live tests only cover news, so keeping this on price balances coverage.
    """
    # Test with invalid symbol
    provider = FinnhubPriceProvider(finnhub_settings, ["INVALID_SYMBOL_XYZ123"])

    # Should not raise, just return empty or skip invalid
    results = await provider.fetch_incremental()

    # Invalid symbols typically return c=0 which we filter out
    assert len(results) == 0 or all(r.price > 0 for r in results)
