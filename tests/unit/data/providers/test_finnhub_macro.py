"""
Tests for FinnhubMacroNewsProvider.
Tests macro news fetching with ID-based pagination (minId parameter).
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubMacroNewsProvider
from data.models import NewsItem


class TestFinnhubMacroNewsProvider:
    """Test FinnhubMacroNewsProvider macro news fetching and parsing"""

    @pytest.mark.asyncio
    async def test_bootstrap_ignores_since_no_minId_param(self):
        """Test first-run behavior when no watermark exists"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL', 'MSFT'])

        # Capture what params were passed to API
        captured_params = {}

        async def mock_get(path, params):
            captured_params.update(params)
            return []  # Empty response

        provider.client.get = AsyncMock(side_effect=mock_get)

        # Call with since parameter (should be ignored in bootstrap mode)
        await provider.fetch_incremental(
            since=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            min_id=None  # Bootstrap mode
        )

        # Verify API was called with category=general but NO minId
        assert captured_params == {'category': 'general'}
        assert 'minId' not in captured_params

    @pytest.mark.asyncio
    async def test_incremental_uses_minId_and_filters_ids_leq(self, monkeypatch):
        """Test incremental fetching with minId watermark"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])

        # Mock API to return articles with various IDs
        mock_articles = [
            {'id': 99, 'headline': 'Old', 'datetime': 1705320000, 'url': 'https://example.com/99', 'related': 'AAPL'},
            {'id': 100, 'headline': 'At boundary', 'datetime': 1705320000, 'url': 'https://example.com/100', 'related': 'AAPL'},
            {'id': 101, 'headline': 'New', 'datetime': 1705320000, 'url': 'https://example.com/101', 'related': 'AAPL'},
        ]

        captured_params = {}

        async def mock_get(path, params):
            captured_params.update(params)
            return mock_articles

        provider.client.get = AsyncMock(side_effect=mock_get)

        # Fetch with min_id=100
        result = await provider.fetch_incremental(min_id=100)

        # Verify API was called with minId
        assert captured_params == {'category': 'general', 'minId': 100}

        # Verify defensive filtering: only articles with id > 100
        assert len(result) == 1
        assert result[0].headline == 'New'

    @pytest.mark.asyncio
    async def test_last_fetched_max_id_updates_only_when_greater(self, monkeypatch):
        """Test watermark advancement logic"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])

        # Scenario 1: Normal progression (max ID advances)
        mock_articles = [
            {'id': 101, 'headline': 'A', 'datetime': 1705320000, 'url': 'https://example.com/101', 'related': 'AAPL'},
            {'id': 102, 'headline': 'B', 'datetime': 1705320000, 'url': 'https://example.com/102', 'related': 'AAPL'},
            {'id': 103, 'headline': 'C', 'datetime': 1705320000, 'url': 'https://example.com/103', 'related': 'AAPL'},
        ]
        provider.client.get = AsyncMock(return_value=mock_articles)

        await provider.fetch_incremental(min_id=100)
        assert provider.last_fetched_max_id == 103

        # Scenario 2: Regression case (API returned older IDs)
        mock_articles_old = [
            {'id': 98, 'headline': 'Old1', 'datetime': 1705320000, 'url': 'https://example.com/98', 'related': 'AAPL'},
            {'id': 99, 'headline': 'Old2', 'datetime': 1705320000, 'url': 'https://example.com/99', 'related': 'AAPL'},
        ]
        provider.client.get = AsyncMock(return_value=mock_articles_old)

        await provider.fetch_incremental(min_id=100)
        # Watermark should NOT regress - stays at None for this batch
        assert provider.last_fetched_max_id is None

        # Scenario 3: Empty/malformed response
        provider.client.get = AsyncMock(return_value=[])
        await provider.fetch_incremental(min_id=100)
        assert provider.last_fetched_max_id is None

    @pytest.mark.asyncio
    async def test_parse_article_multiple_symbols_epoch_to_utc_source_default_summary_to_content(self):
        """Test article parsing logic with all transformations"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL', 'MSFT', 'TSLA'])

        # Mock article with multiple related symbols
        article = {
            'id': 123,
            'headline': 'Market rally',
            'datetime': 1705320000,  # epoch seconds
            'url': 'https://example.com/article',
            'source': 'Reuters',
            'summary': 'Stocks up today',
            'related': 'AAPL,MSFT,GOOG'  # GOOG not in watchlist
        }

        # Parse article
        items = provider._parse_article(article, buffer_time=None)

        # Should return 2 NewsItems (AAPL and MSFT match watchlist, GOOG filtered)
        assert len(items) == 2

        # Check first item (AAPL)
        assert items[0].symbol == 'AAPL'
        assert items[0].headline == 'Market rally'
        assert items[0].published == datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert items[0].source == 'Reuters'
        assert items[0].content == 'Stocks up today'
        assert items[0].url == 'https://example.com/article'

        # Check second item (MSFT)
        assert items[1].symbol == 'MSFT'
        assert items[1].headline == 'Market rally'
        assert items[1].published == datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Test source defaults to 'Finnhub' if missing
        article_no_source = {
            'id': 124,
            'headline': 'Test',
            'datetime': 1705320000,
            'url': 'https://example.com/test',
            'related': 'AAPL'
        }
        items2 = provider._parse_article(article_no_source, buffer_time=None)
        assert items2[0].source == 'Finnhub'

    @pytest.mark.asyncio
    async def test_extract_symbols_related_empty_ALL_mixed_filtered_none_match_empty(self):
        """Test symbol extraction edge cases"""
        settings = FinnhubSettings(api_key='test_key')

        # Case 1: empty related → ALL
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])
        article = {
            'id': 1,
            'headline': 'News',
            'datetime': 1705320000,
            'url': 'https://example.com/1',
            'related': ''
        }
        items = provider._parse_article(article, buffer_time=None)
        assert len(items) == 1
        assert items[0].symbol == 'ALL'

        # Case 2: mixed symbols, only some match watchlist
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])
        article = {
            'id': 2,
            'headline': 'News',
            'datetime': 1705320000,
            'url': 'https://example.com/2',
            'related': 'AAPL,GOOG'
        }
        items = provider._parse_article(article, buffer_time=None)
        assert len(items) == 1
        assert items[0].symbol == 'AAPL'

        # Case 3: no matches → falls back to macro catch-all
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])
        article = {
            'id': 3,
            'headline': 'News',
            'datetime': 1705320000,
            'url': 'https://example.com/3',
            'related': 'XYZ,ABC'
        }
        items = provider._parse_article(article, buffer_time=None)
        assert len(items) == 1
        assert items[0].symbol == 'ALL'

        # Case 4: empty watchlist → treat as macro and tag ALL
        provider = FinnhubMacroNewsProvider(settings, [])
        article = {
            'id': 4,
            'headline': 'News',
            'datetime': 1705320000,
            'url': 'https://example.com/4',
            'related': 'AAPL,MSFT'
        }
        items = provider._parse_article(article, buffer_time=None)
        assert len(items) == 1
        assert items[0].symbol == 'ALL'

        # Case 5: missing 'related' field → ALL
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])
        article = {
            'id': 5,
            'headline': 'News',
            'datetime': 1705320000,
            'url': 'https://example.com/5'
            # No 'related' field
        }
        items = provider._parse_article(article, buffer_time=None)
        assert len(items) == 1
        assert items[0].symbol == 'ALL'

    @pytest.mark.asyncio
    async def test_validate_connection_delegates_to_client(self):
        """Test connection validation delegation"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])

        # Mock client validation to return True
        provider.client.validate_connection = AsyncMock(return_value=True)
        result = await provider.validate_connection()
        assert result is True

        # Mock client validation to return False
        provider.client.validate_connection = AsyncMock(return_value=False)
        result = await provider.validate_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_invalid_shapes_and_epochs_macro(self):
        """Test that invalid data shapes are skipped without crashing"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])

        # 1) Missing headline
        items = provider._parse_article(
            {'id': 1, 'headline': '', 'datetime': 1705320000, 'url': 'https://x', 'related': 'AAPL'},
            buffer_time=None
        )
        assert items == []

        # 2) Missing url
        items = provider._parse_article(
            {'id': 2, 'headline': 'H', 'datetime': 1705320000, 'url': '', 'related': 'AAPL'},
            buffer_time=None
        )
        assert items == []

        # 3) Non-positive epoch
        items = provider._parse_article(
            {'id': 3, 'headline': 'H', 'datetime': 0, 'url': 'https://x', 'related': 'AAPL'},
            buffer_time=None
        )
        assert items == []

    @pytest.mark.asyncio
    async def test_macro_buffer_filters_published_before_or_equal_to_buffer(self):
        """Test 2-minute buffer filters old articles correctly"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubMacroNewsProvider(settings, ['AAPL'])

        # pretend "now" is 2024-01-15T12:00Z; set buffer_time to now-120s = 11:58:00Z
        now = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        buffer_time = now - timedelta(seconds=120)

        # Article at 11:58:00Z (== buffer) MUST be skipped
        at_buffer = {
            'id': 10, 'headline': 'Old', 'datetime': int((now - timedelta(seconds=120)).timestamp()),
            'url': 'https://old', 'related': 'AAPL'
        }
        # Article at 11:59:00Z MUST be kept
        in_window = {
            'id': 11, 'headline': 'Keep', 'datetime': int((now - timedelta(seconds=60)).timestamp()),
            'url': 'https://keep', 'related': 'AAPL'
        }

        kept = provider._parse_article(at_buffer, buffer_time=buffer_time)
        assert kept == []  # filtered at cutoff

        kept = provider._parse_article(in_window, buffer_time=buffer_time)
        assert len(kept) == 1 and kept[0].headline == 'Keep'
