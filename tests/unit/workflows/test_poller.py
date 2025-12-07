"""DataPoller orchestrator: one-cycle behavior and watermarks."""

import asyncio
import logging
import time
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data.base import NewsDataSource, PriceDataSource, SocialDataSource
from data.models import NewsEntry, NewsType, PriceData, Session, SocialDiscussion
from llm.base import LLMError
from tests.factories import make_news_entry, make_price_data, make_social_discussion
from workflows.poller import DataPoller
from workflows.watermarks import CursorPlan


class StubNews(NewsDataSource):
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
    def __init__(self, items: list[PriceData]):
        super().__init__("StubPrice")
        self._items = items

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(self) -> list[PriceData]:
        return self._items


class SecondaryStubPrice(PriceDataSource):
    def __init__(self, items: list[PriceData]):
        super().__init__("SecondaryStubPrice")
        self._items = items

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(self) -> list[PriceData]:
        return self._items


class StubMacroNews(NewsDataSource):
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


class StubSocial(SocialDataSource):
    def __init__(self, items: list[SocialDiscussion]):
        super().__init__("StubSocial")
        self._items = items
        self.last_called_kwargs: dict[str, object | None] | None = None

    async def validate_connection(self) -> bool:
        return True

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        symbol_since_map: Mapping[str, datetime] | None = None,
    ) -> list[SocialDiscussion]:
        self.last_called_kwargs = {
            "since": since,
            "symbol_since_map": symbol_since_map,
        }
        return self._items


class TestDataPoller:
    pytestmark = pytest.mark.asyncio

    async def test_poll_once_collects_errors(self, temp_db):
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

        poller = DataPoller(temp_db, [ErrNews()], [], [StubPrice(ok_prices)], poll_interval=300)

        stats = await poller.poll_once()
        assert stats["news"] == 0
        assert stats["prices"] == 1
        assert stats["errors"] and any(
            "ErrNews" in e for e in stats["errors"]
        )  # provider name included

    async def test_poller_quick_shutdown(self, temp_db):
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)

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
        # Create poller with custom 60 second interval
        custom_interval = 60
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [],
            [StubPrice([])],
            poll_interval=custom_interval,
        )

        # Verify the interval was set correctly
        assert poller.poll_interval == custom_interval

        # Test different interval
        another_poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=120)
        assert another_poller.poll_interval == 120

    async def test_poll_once_collects_price_provider_errors(self, temp_db):
        class ErrPrice(PriceDataSource):
            def __init__(self) -> None:
                super().__init__("ErrPrice")

            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(self) -> list[PriceData]:
                raise RuntimeError("price boom")

        poller = DataPoller(temp_db, [StubNews([])], [], [ErrPrice()], poll_interval=300)

        stats = await poller.poll_once()

        assert stats["prices"] == 0
        assert any("ErrPrice" in message for message in stats["errors"])

    async def test_fetch_all_data_forwards_cursor_kwargs(self, temp_db, monkeypatch):
        provider = StubNews([])
        poller = DataPoller(temp_db, [provider], [], [], poll_interval=60)

        plan = CursorPlan(
            since=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            min_id=42,
            symbol_since_map={"AAPL": datetime(2024, 1, 2, 12, 0, tzinfo=UTC)},
        )
        monkeypatch.setattr(poller.watermarks, "build_plan", lambda _provider: plan)

        captured: dict[str, object | None] = {}

        async def capturing_fetch(**kwargs):
            captured.update(kwargs)
            return []

        provider.fetch_incremental = capturing_fetch  # type: ignore[assignment]

        await poller._fetch_all_data()

        assert captured["since"] == plan.since
        assert captured["min_id"] == plan.min_id
        assert captured["symbol_since_map"] is plan.symbol_since_map

    async def test_fetch_all_data_routes_company_and_macro_news(self, temp_db, monkeypatch):
        """Test fetch all data routes company and macro news."""
        company_entry = make_news_entry(symbol="AAPL", news_type=NewsType.COMPANY_SPECIFIC)
        macro_entry = make_news_entry(symbol="MARKET", news_type=NewsType.MACRO)
        company_provider = StubNews([company_entry])
        macro_provider = StubMacroNews([macro_entry])

        poller = DataPoller(temp_db, [company_provider, macro_provider], [], [], poll_interval=60)

        monkeypatch.setattr(poller.watermarks, "build_plan", lambda _provider: CursorPlan())
        monkeypatch.setattr(
            "workflows.poller.is_macro_stream",
            lambda provider: provider is macro_provider,
        )

        data = await poller._fetch_all_data()

        assert data["company_news"] == [company_entry]
        assert data["macro_news"] == [macro_entry]
        assert data["news_by_provider"][company_provider] == [company_entry]
        assert data["news_by_provider"][macro_provider] == [macro_entry]

    async def test_fetch_all_data_handles_social_providers(self, temp_db, monkeypatch):
        """Social providers receive cursor kwargs and errors are collected."""
        social_item = make_social_discussion(symbol="AAPL")
        social_provider = StubSocial([social_item])
        error_provider = StubSocial([])

        async def failing_fetch(**_kwargs):
            raise RuntimeError("social boom")

        error_provider.fetch_incremental = failing_fetch  # type: ignore[assignment]

        poller = DataPoller(temp_db, [], [social_provider, error_provider], [], poll_interval=60)

        plan = CursorPlan(
            since=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            symbol_since_map={"AAPL": datetime(2024, 1, 1, 0, 0, tzinfo=UTC)},
        )
        monkeypatch.setattr(poller.watermarks, "build_plan", lambda _provider: plan)

        data = await poller._fetch_all_data()

        assert data["social_discussions"] == [social_item]
        assert data["social_by_provider"][social_provider] == [social_item]
        assert "social boom" in "".join(data["errors"])
        assert social_provider.last_called_kwargs == {
            "since": plan.since,
            "symbol_since_map": plan.symbol_since_map,
        }

    async def test_poll_once_logs_no_price_data(self, temp_db, caplog, monkeypatch):
        """Empty price payload logs a notice."""
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)

        async def fake_fetch_all(self):
            return {
                "company_news": [],
                "macro_news": [],
                "social_discussions": [],
                "prices": {},
                "news_by_provider": {},
                "social_by_provider": {},
                "errors": [],
            }

        monkeypatch.setattr(DataPoller, "_fetch_all_data", fake_fetch_all)
        caplog.set_level(logging.INFO)

        await poller.poll_once()

        assert "No price data fetched" in caplog.text

    async def test_poll_once_includes_social_stats(self, temp_db, monkeypatch):
        """Poll stats include social count and surfaced errors."""
        social_item = make_social_discussion()
        provider = StubSocial([social_item])
        poller = DataPoller(temp_db, [], [provider], [], poll_interval=60)

        async def fake_fetch_all(self):
            return {
                "company_news": [],
                "macro_news": [],
                "social_discussions": [social_item],
                "prices": {},
                "news_by_provider": {},
                "social_by_provider": {provider: [social_item]},
                "errors": ["social boom"],
            }

        monkeypatch.setattr(DataPoller, "_fetch_all_data", fake_fetch_all)

        async def fake_process_news(*_args, **_kwargs):
            return 0

        async def fake_process_prices(*_args, **_kwargs):
            return 0

        async def fake_process_social(_self, _map, items):
            return len(items)

        monkeypatch.setattr(DataPoller, "_process_news", fake_process_news)
        monkeypatch.setattr(DataPoller, "_process_prices", fake_process_prices)
        monkeypatch.setattr(DataPoller, "_process_social", fake_process_social)

        stats = await poller.poll_once()

        assert stats["social"] == 1
        assert "social boom" in stats["errors"]

    async def test_poll_once_catches_cycle_error_and_appends(self, temp_db, caplog, monkeypatch):
        """Top-level exceptions are caught and surfaced via stats."""

        async def boom_fetch(*_args, **_kwargs):
            raise ValueError("boom")

        monkeypatch.setattr(DataPoller, "_fetch_all_data", boom_fetch)
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)
        caplog.set_level(logging.ERROR)

        stats = await poller.poll_once()

        assert stats == {"news": 0, "social": 0, "prices": 0, "errors": ["Cycle error: boom"]}
        assert "Poll cycle failed with error: boom" in caplog.text


class TestDataPollerProcessPrices:
    """Focused tests for price deduplication paths."""

    pytestmark = pytest.mark.asyncio

    async def test_process_prices_returns_zero_on_empty_input(self, temp_db, monkeypatch):
        """Test process prices returns zero on empty input."""
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)
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
        """Test process prices primary missing symbol warns and skips."""
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [],
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
        """Test process prices missing secondary provider is ignored."""
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [],
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
        """Test process prices secondary missing symbol warns."""
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [],
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
        """Test process prices mismatch logs error and keeps primary."""
        poller = DataPoller(
            temp_db,
            [StubNews([])],
            [],
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
        """Test process prices handles duplicate class instances."""
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
            [],
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


class TestDataPollerSocialProcessing:
    """Social storage, logging, and watermark handling."""

    @pytest.mark.asyncio
    async def test_process_social_stores_and_commits(self, temp_db, monkeypatch):
        """Stores social discussions and commits watermarks."""
        social_item = make_social_discussion()
        provider = StubSocial([social_item])
        poller = DataPoller(temp_db, [], [provider], [], poll_interval=300)
        social_by_provider = {provider: [social_item]}

        stored: list[SocialDiscussion] = []
        commits: list[tuple[SocialDataSource, list[SocialDiscussion]]] = []

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        def fake_store(_db_path, items):
            stored.extend(items)

        def fake_commit(src, items):
            commits.append((src, items))

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_social_discussions", fake_store)
        monkeypatch.setattr(poller.watermarks, "commit_updates", fake_commit)

        count = await poller._process_social(social_by_provider, [social_item])  # type: ignore[arg-type]

        assert count == 1
        assert stored == [social_item]
        assert commits == [(provider, [social_item])]

    @pytest.mark.asyncio
    async def test_process_social_logs_when_empty(self, temp_db, monkeypatch, caplog):
        """Empty social list logs a notice and returns zero."""
        poller = DataPoller(temp_db, [], [], [], poll_interval=300)

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr(poller.watermarks, "commit_updates", lambda *_: None)
        caplog.set_level(logging.INFO)

        count = await poller._process_social({}, [])

        assert count == 0
        assert "No social discussions to process" in caplog.text


class TestDataPollerNewsProcessing:
    """News storage, urgency, and watermark handling."""

    @pytest.mark.asyncio
    async def test_process_news_commits_each_provider(self, temp_db, monkeypatch):
        """Test process news commits each provider."""
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)
        provider_one = StubNews([make_news_entry(symbol="AAPL")])
        provider_two = StubNews([make_news_entry(symbol="TSLA")])
        news_by_provider: dict[NewsDataSource, list[NewsEntry]] = {
            provider_one: provider_one._items,
            provider_two: provider_two._items,
        }
        company_news = provider_one._items
        macro_news = provider_two._items

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)

        calls: list[tuple[NewsDataSource, list[NewsEntry]]] = []

        def fake_commit(provider, entries):
            calls.append((provider, entries))

        monkeypatch.setattr(poller.watermarks, "commit_updates", fake_commit)
        monkeypatch.setattr("workflows.poller.store_news_items", lambda *_: None)

        count = await poller._process_news(news_by_provider, company_news, macro_news)

        assert count == len(company_news) + len(macro_news)
        assert calls == [
            (provider_one, provider_one._items),
            (provider_two, provider_two._items),
        ]

    @pytest.mark.asyncio
    async def test_process_news_logs_urgency_detection_failures(self, temp_db, monkeypatch, caplog):
        """Test process news logs urgency detection failures."""
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)
        entry = make_news_entry(symbol="AAPL")
        provider = StubNews([entry])
        news_by_provider: dict[NewsDataSource, list[NewsEntry]] = {provider: [entry]}

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr("workflows.poller.store_news_items", lambda *_args: None)
        monkeypatch.setattr(poller.watermarks, "commit_updates", lambda *_: None)

        def raising_detect(_entries):
            raise LLMError("urgency boom")

        monkeypatch.setattr("workflows.poller.detect_urgency", raising_detect)

        caplog.set_level(logging.ERROR)
        count = await poller._process_news(news_by_provider, [entry], [])

        assert count == 1
        assert "Urgency detection failed" in caplog.text

    @pytest.mark.asyncio
    async def test_process_news_logs_when_empty(self, temp_db, monkeypatch, caplog):
        """Test process news logs when empty."""
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
        monkeypatch.setattr(poller.watermarks, "commit_updates", lambda *_: None)
        caplog.set_level(logging.INFO)

        count = await poller._process_news({}, [], [])

        assert count == 0
        assert "No news items to process" in caplog.text

    def test_log_urgent_items_logs_summary(self, temp_db, caplog):
        """Test log urgent items logs summary."""
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=300)
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


class TestDataPollerRunLoop:
    """Exercise run-loop control flow branches."""

    pytestmark = pytest.mark.asyncio

    async def test_run_logs_completed_with_errors(self, temp_db, monkeypatch, caplog):
        """Test run logs completed with errors."""

        async def fake_poll_once(self):
            self.stop()
            return {"news": 0, "social": 0, "prices": 0, "errors": ["boom"]}

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=5)

        await poller.run()

        assert "Cycle #1 completed with errors" in caplog.text

    async def test_run_skips_wait_when_sleep_time_zero(self, temp_db, monkeypatch, caplog):
        """Test run skips wait when sleep time zero."""
        call_count = 0

        async def fake_poll_once(self):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                self.stop()
            return {"news": 0, "social": 0, "prices": 0, "errors": []}

        caplog.set_level(logging.INFO)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=0)

        await poller.run()

        assert "Next poll in" not in caplog.text
        assert call_count >= 2

    async def test_run_handles_wait_timeout(self, temp_db, monkeypatch, caplog):
        """Test run handles wait timeout."""
        call_count = 0

        async def fake_poll_once(self):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                self.stop()
            return {"news": 0, "social": 0, "prices": 0, "errors": []}

        async def fake_wait_for(awaitable, timeout):
            task = asyncio.create_task(awaitable)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            raise TimeoutError

        caplog.set_level(logging.DEBUG)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=1)

        await poller.run()

        assert "Poll wait timeout; continuing to next cycle" in caplog.text

    async def test_run_handles_wait_cancelled(self, temp_db, monkeypatch, caplog):
        """Test run handles wait cancelled."""

        async def fake_poll_once(self):
            return {"news": 0, "social": 0, "prices": 0, "errors": []}

        async def fake_wait_for(awaitable, timeout):
            task = asyncio.create_task(awaitable)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            raise asyncio.CancelledError

        caplog.set_level(logging.INFO)
        monkeypatch.setattr(DataPoller, "poll_once", fake_poll_once)
        monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
        poller = DataPoller(temp_db, [StubNews([])], [], [StubPrice([])], poll_interval=1)

        await poller.run()

        assert "Wait cancelled, exiting..." in caplog.text
