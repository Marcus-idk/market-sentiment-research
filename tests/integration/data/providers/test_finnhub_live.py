"""
Live integration tests for Finnhub provider.
These tests make real API calls and require a valid FINNHUB_API_KEY.
Marked with @pytest.mark.network and @pytest.mark.integration.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubNewsProvider, FinnhubPriceProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_quote_fetch():
    """Test fetching real quote data from Finnhub API"""
    # Check if API key is available
    if not os.environ.get('FINNHUB_API_KEY'):
        pytest.skip("FINNHUB_API_KEY not set, skipping live test")
    
    try:
        settings = FinnhubSettings.from_env()
    except ValueError:
        pytest.skip("FINNHUB_API_KEY not configured properly")
    
    # Test with SPY (always available during market hours)
    provider = FinnhubPriceProvider(settings, ['SPY'])
    
    # Validate connection first
    assert await provider.validate_connection() is True
    
    # Fetch quote
    results = await provider.fetch_incremental()
    
    # Basic validation
    assert len(results) >= 1, "Should get at least one price quote"
    
    spy_quote = results[0]
    assert spy_quote.symbol == 'SPY'
    assert spy_quote.price > 0
    assert isinstance(spy_quote.price, Decimal)
    assert spy_quote.timestamp is not None
    assert spy_quote.timestamp.tzinfo == timezone.utc
    assert spy_quote.session is not None
    
    print(f"Live test: SPY price = ${spy_quote.price} at {spy_quote.timestamp}")


async def test_live_news_fetch():
    """Test fetching real news data from Finnhub API"""
    # Check if API key is available
    if not os.environ.get('FINNHUB_API_KEY'):
        pytest.skip("FINNHUB_API_KEY not set, skipping live test")
    
    try:
        settings = FinnhubSettings.from_env()
    except ValueError:
        pytest.skip("FINNHUB_API_KEY not configured properly")
    
    # Test with AAPL (usually has news)
    provider = FinnhubNewsProvider(settings, ['AAPL'])
    
    # Validate connection first
    assert await provider.validate_connection() is True
    
    # Fetch news from last 3 days
    since = datetime.now(timezone.utc) - timedelta(days=3)
    results = await provider.fetch_incremental(since=since)
    
    # May not always have news, so just validate structure if we get any
    if results:
        # Check first article
        article = results[0]
        assert article.symbol == 'AAPL'
        assert article.headline and len(article.headline) > 0
        assert article.url and article.url.startswith('http')
        assert article.published is not None
        assert article.published.tzinfo == timezone.utc
        assert article.source is not None
        
        print(f"Live test: Found {len(results)} news articles for AAPL")
        print(f"  Latest: {article.headline[:60]}...")
    else:
        print("Live test: No recent news for AAPL (this is normal)")


async def test_live_multiple_symbols():
    """Test fetching data for multiple symbols"""
    # Check if API key is available
    if not os.environ.get('FINNHUB_API_KEY'):
        pytest.skip("FINNHUB_API_KEY not set, skipping live test")
    
    try:
        settings = FinnhubSettings.from_env()
    except ValueError:
        pytest.skip("FINNHUB_API_KEY not configured properly")
    
    # Test with multiple popular symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL']
    provider = FinnhubPriceProvider(settings, symbols)
    
    # Fetch quotes
    results = await provider.fetch_incremental()
    
    # Should get quotes for all symbols (during market hours)
    fetched_symbols = {r.symbol for r in results}
    
    # At least one symbol should have data
    assert len(fetched_symbols) >= 1, "Should get at least one quote"
    
    # All fetched quotes should be valid
    for quote in results:
        assert quote.symbol in symbols
        assert quote.price > 0
        assert isinstance(quote.price, Decimal)
    
    print(f"Live test: Fetched quotes for {len(fetched_symbols)} symbols: {fetched_symbols}")


async def test_live_error_handling():
    """Test error handling with invalid symbol"""
    # Check if API key is available
    if not os.environ.get('FINNHUB_API_KEY'):
        pytest.skip("FINNHUB_API_KEY not set, skipping live test")
    
    try:
        settings = FinnhubSettings.from_env()
    except ValueError:
        pytest.skip("FINNHUB_API_KEY not configured properly")
    
    # Test with invalid symbol
    provider = FinnhubPriceProvider(settings, ['INVALID_SYMBOL_XYZ123'])
    
    # Should not raise, just return empty or skip invalid
    results = await provider.fetch_incremental()
    
    # Invalid symbols typically return c=0 which we filter out
    assert len(results) == 0 or all(r.price > 0 for r in results)
    
    print("Live test: Invalid symbol handled gracefully")
