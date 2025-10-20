"""
Live integration tests for Polygon providers leveraging the real API.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from config.providers.polygon import PolygonSettings
from data.models import NewsItem
from data.providers.polygon.polygon_news import PolygonNewsProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_news_fetch() -> None:
    """Fetch real company news for AAPL."""
    if not os.environ.get("POLYGON_API_KEY"):
        pytest.skip("POLYGON_API_KEY not set, skipping live test")

    try:
        settings = PolygonSettings.from_env()
    except ValueError:
        pytest.skip("POLYGON_API_KEY not configured properly")

    provider = PolygonNewsProvider(settings, ["AAPL"])
    # Validate connection first
    assert await provider.validate_connection() is True
    since = datetime.now(timezone.utc) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)

    if results:
        article = results[0]
        assert isinstance(article, NewsItem)
        assert article.symbol == "AAPL"
        assert article.headline and len(article.headline) > 0
        assert article.url and article.url.startswith("http")
        assert article.published.tzinfo == timezone.utc
        assert article.source is not None

        print(f"Live test: Found {len(results)} AAPL articles; latest: {article.headline[:60]}...")
    else:
        print("Live test: No recent AAPL news (this is normal)")


async def test_live_multiple_symbols() -> None:
    """Fetch company news for multiple symbols (at least one should have items)."""
    if not os.environ.get("POLYGON_API_KEY"):
        pytest.skip("POLYGON_API_KEY not set, skipping live test")

    try:
        settings = PolygonSettings.from_env()
    except ValueError:
        pytest.skip("POLYGON_API_KEY not configured properly")

    symbols = ["AAPL", "MSFT", "GOOGL"]
    provider = PolygonNewsProvider(settings, symbols)
    # Validate connection first (mirror Finnhub style)
    assert await provider.validate_connection() is True

    since = datetime.now(timezone.utc) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)
    fetched_symbols = {r.symbol for r in results}
    # At least one symbol should have data (news may be sparse)
    assert len(fetched_symbols) >= 1

    for item in results:
        assert item.symbol in symbols
        assert item.headline and item.url.startswith("http")
    print(f"Live test: Fetched news for {len(fetched_symbols)} symbols: {fetched_symbols}")


async def test_live_error_handling() -> None:
    """Invalid symbol should be handled gracefully (empty or valid items)."""
    if not os.environ.get("POLYGON_API_KEY"):
        pytest.skip("POLYGON_API_KEY not set, skipping live test")

    try:
        settings = PolygonSettings.from_env()
    except ValueError:
        pytest.skip("POLYGON_API_KEY not configured properly")

    provider = PolygonNewsProvider(settings, ["INVALID_SYMBOL_XYZ123"])
    results = await provider.fetch_incremental(since=datetime.now(timezone.utc) - timedelta(days=2))
    assert len(results) == 0 or all(r.headline and r.url.startswith("http") for r in results)
    print("Live test: Invalid symbol handled gracefully")
