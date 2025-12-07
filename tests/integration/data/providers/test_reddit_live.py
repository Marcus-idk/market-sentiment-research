"""Live integration tests for Reddit social provider using the real API."""

from datetime import UTC

import pytest

from data.providers.reddit import RedditSocialProvider

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_live_validate_connection(reddit_settings):
    """Test validating Reddit credentials against the live API."""
    provider = RedditSocialProvider(reddit_settings, ["AAPL"])

    assert await provider.validate_connection() is True


async def test_live_discussions_fetch(reddit_settings):
    """Test fetching recent discussions for a real symbol."""
    provider = RedditSocialProvider(reddit_settings, ["AAPL"])

    results = await provider.fetch_incremental(since=None)

    assert isinstance(results, list)
    assert results  # expect at least one discussion for AAPL

    for item in results:
        assert item.source_id
        assert item.symbol
        assert item.community
        assert item.title
        assert item.url.startswith("http")
        assert item.published.tzinfo is UTC
