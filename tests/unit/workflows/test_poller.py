"""
Unit tests for DataPoller orchestrator.

Covers one-cycle behavior: storing items, watermark update, and
error aggregation. Uses stub providers and the temp_db fixture.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from workflows.poller import DataPoller
from data.base import NewsDataSource, PriceDataSource
from data.models import NewsItem, PriceData, Session
from data.storage import (
    get_last_news_time,
    get_news_since,
    get_price_data_since,
)


class StubNews(NewsDataSource):
    """Stub news provider returning a preset list of items."""

    def __init__(self, items: List[NewsItem]):
        super().__init__("StubNews")
        self._items = items

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(self, since: Optional[datetime] = None) -> List[NewsItem]:
        return self._items


class StubPrice(PriceDataSource):
    """Stub price provider returning a preset list of items."""

    def __init__(self, items: List[PriceData]):
        super().__init__("StubPrice")
        self._items = items

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(self, since: Optional[datetime] = None) -> List[PriceData]:
        return self._items


class TestDataPoller:
    """Tests for the DataPoller orchestrator."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_poll_once_collects_errors(self, temp_db):
        """Aggregates errors from failing providers without aborting cycle."""

        class ErrNews(NewsDataSource):
            def __init__(self):
                super().__init__("ErrNews")

            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(self, since: Optional[datetime] = None) -> List[NewsItem]:
                raise RuntimeError("boom")

        ok_prices = [
            PriceData("AAPL", datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc), Decimal("1.00")),
        ]

        poller = DataPoller(temp_db, [ErrNews()], [StubPrice(ok_prices)], poll_interval=300)

        stats = await poller.poll_once()
        assert stats["news"] == 0
        assert stats["prices"] == 1
        assert stats["errors"] and any("ErrNews" in e for e in stats["errors"])  # provider name included

    @pytest.mark.asyncio
    async def test_poll_once_no_data_no_watermark(self, temp_db):
        """No data returned → stats zero and watermark remains None."""
        assert get_last_news_time(temp_db) is None  # precondition

        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)
        stats = await poller.poll_once()

        assert stats["news"] == 0
        assert stats["prices"] == 0
        assert stats["errors"] == []
        assert get_last_news_time(temp_db) is None  # unchanged

    @pytest.mark.asyncio
    async def test_poller_quick_shutdown(self, temp_db):
        """Verify poller stops quickly when stop() is called during sleep."""
        import time

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

    @pytest.mark.asyncio
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
