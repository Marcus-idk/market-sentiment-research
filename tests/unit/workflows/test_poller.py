"""
Unit tests for DataPoller orchestrator.

Covers one-cycle behavior: storing items, watermark update, and
error aggregation. Uses stub providers and the temp_db fixture.
"""

import asyncio
import pytest
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

pytestmark = pytest.mark.asyncio

from workflows.poller import DataPoller
from data.base import NewsDataSource, PriceDataSource
from data.models import NewsItem, PriceData, Session
from data.storage import (
    get_last_news_time,
    get_news_since,
    get_price_data_since,
    set_last_macro_min_id,
    get_last_macro_min_id,
)


class StubNews(NewsDataSource):
    """Stub news provider returning a preset list of items."""

    def __init__(self, items: list[NewsItem]):
        super().__init__("StubNews")
        self._items = items
        self.last_called_with_since: datetime | None = None

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
    ) -> list[NewsItem]:
        self.last_called_with_since = since
        return self._items


class StubPrice(PriceDataSource):
    """Stub price provider returning a preset list of items."""

    def __init__(self, items: list[PriceData]):
        super().__init__("StubPrice")
        self._items = items

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
    ) -> list[PriceData]:
        return self._items


class StubMacroNews(NewsDataSource):
    """Stub macro news provider that tracks parameters and returns preset items."""

    def __init__(self, items: list[NewsItem]):
        super().__init__("StubMacroNews")
        self._items = items
        self.last_fetched_max_id: int | None = None
        self.last_called_with_since: datetime | None = None
        self.last_called_with_min_id: int | None = None

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(
        self,
        *,
        min_id: int | None = None,
    ) -> list[NewsItem]:
        # Track what parameters we were called with
        self.last_called_with_min_id = min_id
        self.last_called_with_since = None
        return self._items


class TestDataPoller:
    """Tests for the DataPoller orchestrator."""

    async def test_poll_once_stores_and_updates_watermark(self, temp_db):
        """Stores news/prices and sets watermark to max published."""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 15, 10, 5, tzinfo=timezone.utc)

        news = [
            NewsItem("AAPL", "https://example.com/n1", "h1", t1, "S"),
            NewsItem("AAPL", "https://example.com/n2", "h2", t2, "S"),
        ]
        prices = [
            PriceData("AAPL", t2, Decimal("123.45"), session=Session.REG),
        ]

        poller = DataPoller(temp_db, [StubNews(news)], [StubPrice(prices)], poll_interval=300)

        stats = await poller.poll_once()
        assert stats["news"] == 2
        assert stats["prices"] == 1
        assert stats["errors"] == []

        # DB assertions
        assert len(get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))) == 2
        assert len(get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))) == 1
        assert get_last_news_time(temp_db) == t2  # watermark = max published

    async def test_poll_once_collects_errors(self, temp_db):
        """Aggregates errors from failing providers without aborting cycle."""

        class ErrNews(NewsDataSource):
            def __init__(self):
                super().__init__("ErrNews")

            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(
                self,
                *,
                since: datetime | None = None,
                min_id: int | None = None,
            ) -> list[NewsItem]:
                raise RuntimeError("boom")

        ok_prices = [
            PriceData("AAPL", datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc), Decimal("1.00")),
        ]

        poller = DataPoller(temp_db, [ErrNews()], [StubPrice(ok_prices)], poll_interval=300)

        stats = await poller.poll_once()
        assert stats["news"] == 0
        assert stats["prices"] == 1
        assert stats["errors"] and any("ErrNews" in e for e in stats["errors"])  # provider name included

    async def test_poll_once_no_data_no_watermark(self, temp_db):
        """No data returned → stats zero and watermark remains None."""
        assert get_last_news_time(temp_db) is None  # precondition

        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)
        stats = await poller.poll_once()

        assert stats["news"] == 0
        assert stats["prices"] == 0
        assert stats["errors"] == []
        assert get_last_news_time(temp_db) is None  # unchanged

    async def test_poller_quick_shutdown(self, temp_db):
        """Verify poller stops quickly when stop() is called during sleep."""
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)

        # Start poller in background
        run_task = asyncio.create_task(poller.run())

        # Wait for first cycle to complete and enter sleep
        await asyncio.sleep(1)

        # Record time and trigger stop
        start_time = time.time()
        poller.stop()

        # Wait for poller to actually stop
        await run_task

        # Verify it stopped quickly (within 2 seconds, not 300)
        elapsed = time.time() - start_time
        assert elapsed < 2.0, f"Shutdown took {elapsed:.1f}s, expected < 2s"

    async def test_poller_custom_poll_interval(self, temp_db):
        """Verify poll interval is set correctly."""
        # Create poller with custom 60 second interval
        custom_interval = 60
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [StubPrice([])],
            poll_interval=custom_interval
        )

        # Verify the interval was set correctly
        assert poller.poll_interval == custom_interval

        # Test different interval
        another_poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=120)
        assert another_poller.poll_interval == 120

    async def test_macro_provider_receives_min_id_and_results_routed(self, temp_db, monkeypatch):
        """Test provider dispatch logic: both providers receive min_id; results routed by type"""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)

        # Set initial watermark
        set_last_macro_min_id(temp_db, 100)

        # Create distinct news items for each provider
        company_news = [
            NewsItem("AAPL", "https://example.com/company", "Company news", t1, "S"),
        ]
        macro_news = [
            NewsItem("ALL", "https://example.com/macro", "Macro news", t1, "S"),
        ]

        # Create providers
        company_provider = StubNews(company_news)
        macro_provider = StubMacroNews(macro_news)
        macro_provider.last_fetched_max_id = 150  # Simulate watermark update

        # Create poller with both providers
        poller = DataPoller(
            temp_db,
            [company_provider, macro_provider],
            [StubPrice([])],
            poll_interval=300
        )

        # Explicitly mark macro provider without patching builtins
        poller._macro_providers = {macro_provider}

        stats = await poller.poll_once()

        # Verify both providers were called
        assert company_provider.last_called_with_since is None  # First run, no watermark

        assert macro_provider.last_called_with_min_id == 100  # Macro provider gets min_id watermark

        # Verify both sets of news were stored
        assert stats["news"] == 2
        stored_news = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(stored_news) == 2

        # Verify macro watermark was updated
        assert get_last_macro_min_id(temp_db) == 150

    async def test_updates_news_since_iso_and_macro_min_id_independently(self, temp_db, monkeypatch):
        """Test dual watermark updates: datetime and integer advance independently"""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 15, 10, 5, tzinfo=timezone.utc)

        # Set initial watermarks
        set_last_macro_min_id(temp_db, 100)

        # Create news with different timestamps
        company_news = [
            NewsItem("AAPL", "https://example.com/c1", "Company 1", t1, "S"),
            NewsItem("AAPL", "https://example.com/c2", "Company 2", t2, "S"),  # Latest timestamp
        ]
        macro_news = [
            NewsItem("ALL", "https://example.com/m1", "Macro 1", t1, "S"),
        ]

        # Create providers
        company_provider = StubNews(company_news)
        macro_provider = StubMacroNews(macro_news)
        macro_provider.last_fetched_max_id = 150  # New max ID

        # Create poller
        poller = DataPoller(
            temp_db,
            [company_provider, macro_provider],
            [StubPrice([])],
            poll_interval=300
        )

        # Explicitly mark macro provider without patching builtins
        poller._macro_providers = {macro_provider}

        await poller.poll_once()

        # Verify news_since_iso advanced to latest timestamp (t2)
        assert get_last_news_time(temp_db) == t2

        # Verify macro_news_min_id advanced independently to 150
        assert get_last_macro_min_id(temp_db) == 150

    async def test_macro_news_skips_classification_company_only_called(self, temp_db, monkeypatch):
        """Test classification routing: company news classified, macro skipped"""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)

        # Create distinct news items
        company_news = [
            NewsItem("AAPL", "https://example.com/company", "Company news", t1, "S"),
        ]
        macro_news = [
            NewsItem("ALL", "https://example.com/macro", "Macro news", t1, "S"),
        ]

        # Create providers
        company_provider = StubNews(company_news)
        macro_provider = StubMacroNews(macro_news)

        # Track what was passed to classify()
        classify_called_with = []

        def mock_classify(news_items):
            classify_called_with.extend(news_items)
            return []  # Return empty labels

        # Patch classify function
        with patch('workflows.poller.classify', side_effect=mock_classify):
            # Create poller
            poller = DataPoller(
                temp_db,
                [company_provider, macro_provider],
                [StubPrice([])],
                poll_interval=300
            )

            # Explicitly mark macro provider without patching builtins
            poller._macro_providers = {macro_provider}

            await poller.poll_once()

        # Verify classify was called with ONLY company news
        assert len(classify_called_with) == 1
        assert classify_called_with[0].symbol == 'AAPL'
        assert classify_called_with[0].headline == 'Company news'

        # Verify macro news was NOT passed to classify
        assert not any(item.symbol == 'ALL' for item in classify_called_with)
