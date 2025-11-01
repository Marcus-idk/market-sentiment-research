"""
Live integration tests for Polygon providers leveraging the real API.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from config.providers.polygon import PolygonSettings
from data.models import NewsEntry
from data.providers.polygon import PolygonNewsProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_news_fetch():
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
    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)

    if results:
        entry = results[0]
        assert isinstance(entry, NewsEntry)
        assert entry.symbol == "AAPL", "fetched symbol should match request"
        assert entry.headline and len(entry.headline) > 0
        assert entry.url and entry.url.startswith("http"), "url should be http(s)"
        assert entry.published.tzinfo == UTC, "timestamps must be UTC"
        assert entry.source is not None


async def test_live_multiple_symbols():
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

    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)
    fetched_symbols = {r.symbol for r in results}
    # At least one symbol should have data (news may be sparse)
    assert len(fetched_symbols) >= 1

    for item in results:
        assert item.symbol in symbols, "item symbol should be from requested set"
        assert item.headline and item.url.startswith("http"), "headline present and url http(s)"


async def test_live_error_handling():
    """Invalid symbol should be handled gracefully (empty or valid items)."""
    if not os.environ.get("POLYGON_API_KEY"):
        pytest.skip("POLYGON_API_KEY not set, skipping live test")

    try:
        settings = PolygonSettings.from_env()
    except ValueError:
        pytest.skip("POLYGON_API_KEY not configured properly")

    provider = PolygonNewsProvider(settings, ["INVALID_SYMBOL_XYZ123"])
    results = await provider.fetch_incremental(since=datetime.now(UTC) - timedelta(days=2))
    assert len(results) == 0 or all(
        isinstance(r, NewsEntry) and r.headline and r.url.startswith("http") for r in results
    ), "invalid symbol should yield no results or valid-shaped items"
