"""DataPoller orchestrator: one-cycle behavior and watermarks."""

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data.base import NewsDataSource, PriceDataSource
from data.models import NewsEntry, NewsItem, NewsType, PriceData, Session
from data.storage import (
    get_last_macro_min_id,
    get_last_news_time,
    get_news_since,
    get_price_data_since,
    set_last_macro_min_id,
)
from workflows.poller import DataPoller

pytestmark = pytest.mark.asyncio


def _make_entry(
    *,
    symbol: str,
    url_suffix: str,
    headline: str,
    published: datetime,
    news_type: NewsType,
) -> NewsEntry:
    article = NewsItem(
        url=f"https://example.com/{url_suffix}",
        headline=headline,
        source="StubSource",
        published=published,
        news_type=news_type,
        content=None,
    )
    return NewsEntry(article=article, symbol=symbol, is_important=None)


class StubNews(NewsDataSource):
    """Stub news provider returning a preset list of items."""

    def __init__(self, items: list[NewsEntry]):
        super().__init__("StubNews")
        self._items = items
        self.last_called_with_since: datetime | None = None

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
    ) -> list[NewsEntry]:
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

    def __init__(self, items: list[NewsEntry]):
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
    ) -> list[NewsEntry]:
        # Track what parameters we were called with
        self.last_called_with_min_id = min_id
        self.last_called_with_since = None
        return self._items


class TestDataPoller:
    """Tests for the DataPoller orchestrator."""

    async def test_poll_once_stores_and_updates_watermark(self, temp_db):
        """Stores news/prices and sets watermark to max published."""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        t2 = datetime(2024, 1, 15, 10, 5, tzinfo=UTC)

        news = [
            _make_entry(
                symbol="AAPL",
                url_suffix="n1",
                headline="h1",
                published=t1,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            _make_entry(
                symbol="AAPL",
                url_suffix="n2",
                headline="h2",
                published=t2,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
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
        assert len(get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))) == 2
        assert len(get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))) == 1
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
            ) -> list[NewsEntry]:
                raise RuntimeError("boom")

        ok_prices = [
            PriceData("AAPL", datetime(2024, 1, 15, 10, 0, tzinfo=UTC), Decimal("1.00")),
        ]

        poller = DataPoller(temp_db, [ErrNews()], [StubPrice(ok_prices)], poll_interval=300)

        stats = await poller.poll_once()
        assert stats["news"] == 0
        assert stats["prices"] == 1
        assert stats["errors"] and any(
            "ErrNews" in e for e in stats["errors"]
        )  # provider name included

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
            poll_interval=custom_interval,
        )

        # Verify the interval was set correctly
        assert poller.poll_interval == custom_interval

        # Test different interval
        another_poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=120)
        assert another_poller.poll_interval == 120

    async def test_macro_provider_min_id_passed_and_watermark_updated(self, temp_db):
        """Macro providers consume min_id watermark and update it after fetch."""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        # Set initial watermark
        set_last_macro_min_id(temp_db, 100)

        # Create distinct news items for each provider
        company_news = [
            _make_entry(
                symbol="AAPL",
                url_suffix="company",
                headline="Company news",
                published=t1,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
        ]
        macro_news = [
            _make_entry(
                symbol="MARKET",
                url_suffix="macro",
                headline="Macro news",
                published=t1,
                news_type=NewsType.MACRO,
            ),
        ]

        # Create providers
        company_provider = StubNews(company_news)
        macro_provider = StubMacroNews(macro_news)
        macro_provider.last_fetched_max_id = 150  # Simulate watermark update

        # Create poller with both providers
        poller = DataPoller(
            temp_db, [company_provider, macro_provider], [StubPrice([])], poll_interval=300
        )

        # Explicitly mark macro provider without patching builtins
        poller._finnhub_macro_providers = {macro_provider}

        stats = await poller.poll_once()

        # Verify both providers were called
        assert company_provider.last_called_with_since is None  # First run, no watermark

        # Macro provider gets min_id watermark
        assert macro_provider.last_called_with_min_id == 100

        # Verify both sets of news were stored
        assert stats["news"] == 2
        stored_news = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        assert len(stored_news) == 2
        symbols = {entry.symbol for entry in stored_news}
        assert symbols == {"AAPL", "MARKET"}

        # Verify macro watermark was updated
        assert get_last_macro_min_id(temp_db) == 150

    async def test_updates_news_since_iso_and_macro_min_id_independently(self, temp_db):
        """Test dual watermark updates: datetime and integer advance independently"""
        t1 = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        t2 = datetime(2024, 1, 15, 10, 5, tzinfo=UTC)

        # Set initial watermarks
        set_last_macro_min_id(temp_db, 100)

        # Create news with different timestamps
        company_news = [
            _make_entry(
                symbol="AAPL",
                url_suffix="c1",
                headline="Company 1",
                published=t1,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            _make_entry(
                symbol="AAPL",
                url_suffix="c2",
                headline="Company 2",
                published=t2,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),  # Latest timestamp
        ]
        macro_news = [
            _make_entry(
                symbol="MARKET",
                url_suffix="m1",
                headline="Macro 1",
                published=t1,
                news_type=NewsType.MACRO,
            ),
        ]

        # Create providers
        company_provider = StubNews(company_news)
        macro_provider = StubMacroNews(macro_news)
        macro_provider.last_fetched_max_id = 150  # New max ID

        # Create poller
        poller = DataPoller(
            temp_db, [company_provider, macro_provider], [StubPrice([])], poll_interval=300
        )

        # Explicitly mark macro provider without patching builtins
        poller._finnhub_macro_providers = {macro_provider}

        await poller.poll_once()

        # Verify news_since_iso advanced to latest timestamp (t2)
        assert get_last_news_time(temp_db) == t2

        # Verify macro_news_min_id advanced independently to 150
        assert get_last_macro_min_id(temp_db) == 150
