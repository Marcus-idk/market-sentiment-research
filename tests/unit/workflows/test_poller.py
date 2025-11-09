"""DataPoller orchestrator: one-cycle behavior and watermarks."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data.base import NewsDataSource, PriceDataSource
from data.models import NewsEntry, NewsType, PriceData, Session
from data.storage import (
    get_last_macro_min_id,
    get_last_news_time,
    get_news_since,
    get_price_data_since,
    set_last_macro_min_id,
    set_last_news_time,
)
from llm.base import LLMError
from tests.factories import make_news_entry, make_price_data
from workflows.poller import DataPoller

pytestmark = pytest.mark.asyncio


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


class SecondaryStubPrice(PriceDataSource):
    """Secondary stub price provider."""

    def __init__(self, items: list[PriceData]):
        super().__init__("SecondaryStubPrice")
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
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/n1",
                headline="h1",
                source="StubSource",
                published=t1,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/n2",
                headline="h2",
                source="StubSource",
                published=t2,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
        ]
        prices = [
            make_price_data(
                symbol="AAPL",
                timestamp=t2,
                price=Decimal("123.45"),
                session=Session.REG,
            ),
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
            make_price_data(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                price=Decimal("1.00"),
            ),
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
        assert elapsed < 2.0

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
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/company",
                headline="Company news",
                source="StubSource",
                published=t1,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
        ]
        macro_news = [
            make_news_entry(
                symbol="MARKET",
                url="https://example.com/macro",
                headline="Macro news",
                source="StubSource",
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
        poller._finnhub_macro_providers = {macro_provider}  # type: ignore[reportAttributeAccessIssue]

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
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/c1",
                headline="Company 1",
                source="StubSource",
                published=t1,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),
            make_news_entry(
                symbol="AAPL",
                url="https://example.com/c2",
                headline="Company 2",
                source="StubSource",
                published=t2,
                news_type=NewsType.COMPANY_SPECIFIC,
            ),  # Latest timestamp
        ]
        macro_news = [
            make_news_entry(
                symbol="MARKET",
                url="https://example.com/m1",
                headline="Macro 1",
                source="StubSource",
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
        poller._finnhub_macro_providers = {macro_provider}  # type: ignore[reportAttributeAccessIssue]

        await poller.poll_once()

        # Verify news_since_iso advanced to latest timestamp (t2)
        assert get_last_news_time(temp_db) == t2

        # Verify macro_news_min_id advanced independently to 150
        assert get_last_macro_min_id(temp_db) == 150

    async def test_poll_once_collects_price_provider_errors(self, temp_db):
        """Price provider failures are reported without aborting the cycle."""

        class ErrPrice(PriceDataSource):
            def __init__(self) -> None:
                super().__init__("ErrPrice")

            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(
                self,
                *,
                since: datetime | None = None,
            ) -> list[PriceData]:
                raise RuntimeError("price boom")

        poller = DataPoller(temp_db, [StubNews([])], [ErrPrice()], poll_interval=300)

        stats = await poller.poll_once()

        assert stats["prices"] == 0
        assert any("ErrPrice" in message for message in stats["errors"])

    async def test_poll_once_logs_since_when_watermark_present(self, temp_db, caplog, monkeypatch):
        """Existing watermark is logged before fetching."""
        watermark = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        set_last_news_time(temp_db, watermark)
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)

        async def fake_fetch_all(self, last_news_time, last_macro_min_id):
            assert last_news_time == watermark
            return {
                "company_news": [],
                "macro_news": [],
                "prices": {},
                "errors": [],
            }

        monkeypatch.setattr(DataPoller, "_fetch_all_data", fake_fetch_all)
        caplog.set_level(logging.INFO)

        stats = await poller.poll_once()

        assert stats == {"news": 0, "prices": 0, "errors": []}
        assert "Fetching news since" in caplog.text

    async def test_poll_once_logs_no_price_data(self, temp_db, caplog, monkeypatch):
        """Empty price payload logs a notice."""
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)

        async def fake_fetch_all(self, last_news_time, last_macro_min_id):
            return {
                "company_news": [],
                "macro_news": [],
                "prices": {},
                "errors": [],
            }

        monkeypatch.setattr(DataPoller, "_fetch_all_data", fake_fetch_all)
        caplog.set_level(logging.INFO)

        await poller.poll_once()

        assert "No price data fetched" in caplog.text

    async def test_poll_once_catches_cycle_error_and_appends(self, temp_db, caplog, monkeypatch):
        """Top-level exceptions are caught and surfaced via stats."""

        async def boom_fetch(*_args, **_kwargs):
            raise ValueError("boom")

        monkeypatch.setattr(DataPoller, "_fetch_all_data", boom_fetch)
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)
        caplog.set_level(logging.ERROR)

        stats = await poller.poll_once()

        assert stats == {"news": 0, "prices": 0, "errors": ["Cycle error: boom"]}
        assert "Poll cycle failed with error: boom" in caplog.text


class TestDataPollerProcessPrices:
    """Focused tests for price deduplication paths."""

    async def test_process_prices_returns_zero_on_empty_input(self, temp_db, monkeypatch):
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)
        stored: list[PriceData] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, prices):
            stored.extend(prices)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_price_data", fake_store)

        result = await poller._process_prices({})

        assert result == 0
        assert stored == []

    async def test_process_prices_primary_missing_symbol_warns_and_skips(
        self, temp_db, monkeypatch, caplog
    ):
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [StubPrice([]), SecondaryStubPrice([])],
            poll_interval=300,
        )
        stored: list[PriceData] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, prices):
            stored.extend(prices)

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_price_data", fake_store)

        secondary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.00"),
            session=Session.REG,
        )
        primary_provider, secondary_provider = poller.price_providers

        result = await poller._process_prices(
            {
                primary_provider: {},
                secondary_provider: {"AAPL": secondary_price},
            }
        )

        assert result == 0
        assert stored == []
        assert "StubPrice missing price for AAPL" in caplog.text

    async def test_process_prices_missing_secondary_provider_is_ignored(self, temp_db, monkeypatch):
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [StubPrice([]), SecondaryStubPrice([])],
            poll_interval=300,
        )
        stored: list[PriceData] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, prices):
            stored.extend(prices)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_price_data", fake_store)

        primary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.00"),
            session=Session.REG,
        )
        primary_provider = poller.price_providers[0]

        result = await poller._process_prices({primary_provider: {"AAPL": primary_price}})

        assert result == 1
        assert stored == [primary_price]

    async def test_process_prices_secondary_missing_symbol_warns(
        self, temp_db, monkeypatch, caplog
    ):
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [StubPrice([]), SecondaryStubPrice([])],
            poll_interval=300,
        )
        stored: list[PriceData] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, prices):
            stored.extend(prices)

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_price_data", fake_store)

        primary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.00"),
            session=Session.REG,
        )
        primary_provider, secondary_provider = poller.price_providers

        result = await poller._process_prices(
            {
                primary_provider: {"AAPL": primary_price},
                secondary_provider: {},
            }
        )

        assert result == 1
        assert stored == [primary_price]
        assert "SecondaryStubPrice missing price for AAPL" in caplog.text

    async def test_process_prices_mismatch_logs_error_and_keeps_primary(
        self, temp_db, monkeypatch, caplog
    ):
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [StubPrice([]), SecondaryStubPrice([])],
            poll_interval=300,
        )
        stored: list[PriceData] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, prices):
            stored.extend(prices)

        caplog.set_level(logging.ERROR)
        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_price_data", fake_store)

        primary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.00"),
            session=Session.REG,
        )
        secondary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.02"),
            session=Session.REG,
        )
        primary_provider, secondary_provider = poller.price_providers

        result = await poller._process_prices(
            {
                primary_provider: {"AAPL": primary_price},
                secondary_provider: {"AAPL": secondary_price},
            }
        )

        assert result == 1
        assert stored == [primary_price]
        assert "Price mismatch for AAPL" in caplog.text

    async def test_process_prices_handles_duplicate_class_instances(
        self, temp_db, monkeypatch, caplog
    ):
        primary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.00"),
            session=Session.REG,
        )
        secondary_price = make_price_data(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            price=Decimal("10.02"),
            session=Session.REG,
        )

        primary_provider = StubPrice([])
        secondary_provider = StubPrice([])

        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [primary_provider, secondary_provider],
            poll_interval=300,
        )

        stored: list[PriceData] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, prices):
            stored.extend(prices)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_price_data", fake_store)
        caplog.set_level(logging.ERROR)

        result = await poller._process_prices(
            {
                primary_provider: {"AAPL": primary_price},
                secondary_provider: {"AAPL": secondary_price},
            }
        )

        assert result == 1
        assert stored == [primary_price]
        assert "Price mismatch for AAPL" in caplog.text


class TestDataPollerNewsProcessing:
    """News storage, urgency, and watermark handling."""

    def test_log_urgent_items_logs_summary(self, temp_db, caplog):
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)
        caplog.set_level(logging.WARNING)
        urgent_items = [
            make_news_entry(
                symbol=f"SYM{i}",
                url=f"https://example.com/urgent-{i}",
                headline=f"Urgent headline {i}",
                source="StubSource",
                published=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            )
            for i in range(11)
        ]

        poller._log_urgent_items(urgent_items)

        assert "Found 11 URGENT news items requiring attention" in caplog.text
        assert "... 1 more" in caplog.text

    async def test_process_news_urgency_detection_failure_is_logged(
        self, temp_db, monkeypatch, caplog
    ):
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)
        news_item = make_news_entry(
            symbol="AAPL",
            url="https://example.com/aapl",
            headline="AAPL update",
            source="StubSource",
            published=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        )

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def raising_detect(_entries):
            raise LLMError("urgency boom")

        caplog.set_level(logging.ERROR)
        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.detect_urgency", raising_detect)

        count = await poller._process_news([news_item], [])

        assert count == 1
        assert "Urgency detection failed" in caplog.text

    async def test_process_news_no_items_logs(self, temp_db, monkeypatch, caplog):
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=300)

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        caplog.set_level(logging.INFO)

        count = await poller._process_news([], [])

        assert count == 0
        assert "No news items to process" in caplog.text

    async def test_process_news_updates_macro_watermark(self, temp_db, monkeypatch):
        published = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        macro_news = [
            make_news_entry(
                symbol="MARKET",
                url="https://example.com/macro",
                headline="Macro headline",
                source="StubSource",
                published=published,
            )
        ]
        macro_provider = StubMacroNews(macro_news)
        macro_provider.last_fetched_max_id = 150
        poller = DataPoller(temp_db, [macro_provider], [StubPrice([])], poll_interval=300)
        poller._finnhub_macro_providers = {macro_provider}  # type: ignore[reportAttributeAccessIssue]

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.detect_urgency", lambda entries: [])

        await poller._process_news([], macro_news)

        assert get_last_news_time(temp_db) == published
        assert get_last_macro_min_id(temp_db) == 150


class TestDataPollerRunLoop:
    """Exercise run-loop control flow branches."""

    async def test_run_logs_completed_with_errors(self, temp_db, monkeypatch, caplog):
        async def fake_poll_once(self):
            self.stop()
            return {"news": 0, "prices": 0, "errors": ["boom"]}

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=5)

        await poller.run()

        assert "Cycle #1 completed with errors" in caplog.text

    async def test_run_skips_wait_when_sleep_time_zero(self, temp_db, monkeypatch, caplog):
        call_count = 0

        async def fake_poll_once(self):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                self.stop()
            return {"news": 0, "prices": 0, "errors": []}

        caplog.set_level(logging.INFO)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=0)

        await poller.run()

        assert "Next poll in" not in caplog.text
        assert call_count >= 2

    async def test_run_handles_wait_timeout(self, temp_db, monkeypatch, caplog):
        call_count = 0

        async def fake_poll_once(self):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                self.stop()
            return {"news": 0, "prices": 0, "errors": []}

        async def fake_wait_for(_awaitable, timeout):
            raise TimeoutError

        caplog.set_level(logging.DEBUG)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=1)

        await poller.run()

        assert "Poll wait timeout; continuing to next cycle" in caplog.text

    async def test_run_handles_wait_cancelled(self, temp_db, monkeypatch, caplog):
        async def fake_poll_once(self):
            return {"news": 0, "prices": 0, "errors": []}

        async def fake_wait_for(_awaitable, timeout):
            raise asyncio.CancelledError

        caplog.set_level(logging.INFO)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        poller = DataPoller(temp_db, [StubNews([])], [StubPrice([])], poll_interval=1)

        await poller.run()

        assert "Wait cancelled, exiting..." in caplog.text
