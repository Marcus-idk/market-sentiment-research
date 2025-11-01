"""
Live integration tests for Polygon providers leveraging the real API.
"""

from datetime import UTC, datetime, timedelta

import pytest

from data.models import NewsEntry
from data.providers.polygon import PolygonNewsProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_news_fetch(polygon_settings):
    """Fetch real company news for AAPL."""
    provider = PolygonNewsProvider(polygon_settings, ["AAPL"])
    # Validate connection first
    assert await provider.validate_connection() is True
    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)

    if results:
        entry = results[0]
        assert isinstance(entry, NewsEntry)
        assert entry.symbol == "AAPL"
        assert entry.headline and len(entry.headline) > 0
        assert entry.url and entry.url.startswith("http")
        assert entry.published.tzinfo == UTC
        assert entry.source is not None


async def test_live_multiple_symbols(polygon_settings):
    """Fetch company news for multiple symbols (at least one should have items)."""
    symbols = ["AAPL", "MSFT", "GOOGL"]
    provider = PolygonNewsProvider(polygon_settings, symbols)
    # Validate connection first (mirror Finnhub style)
    assert await provider.validate_connection() is True

    since = datetime.now(UTC) - timedelta(days=2)
    results = await provider.fetch_incremental(since=since)

    assert isinstance(results, list)
    fetched_symbols = {r.symbol for r in results}
    # At least one symbol should have data (news may be sparse)
    assert len(fetched_symbols) >= 1

    for item in results:
        assert item.symbol in symbols
        assert item.headline and item.url.startswith("http")


async def test_live_error_handling(polygon_settings):
    """Invalid symbol should be handled gracefully (empty or valid items)."""
    provider = PolygonNewsProvider(polygon_settings, ["INVALID_SYMBOL_XYZ123"])
    results = await provider.fetch_incremental(since=datetime.now(UTC) - timedelta(days=2))
    assert len(results) == 0 or all(
        isinstance(r, NewsEntry) and r.headline and r.url.startswith("http") for r in results
    )
