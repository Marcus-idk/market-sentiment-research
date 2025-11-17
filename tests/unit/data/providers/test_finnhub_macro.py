"""Finnhub-specific macro news tests that complement contract coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubMacroNewsProvider


@pytest.fixture
def macro_provider() -> FinnhubMacroNewsProvider:
    settings = FinnhubSettings(api_key="test_key")
    return FinnhubMacroNewsProvider(settings, ["AAPL", "MSFT"])


pytestmark = pytest.mark.asyncio


class TestFinnhubMacroProviderSpecific:
    """Tests for Finnhub-only behaviors not covered by macro contracts."""

    async def test_fetch_incremental_includes_min_id_param(
        self, macro_provider: FinnhubMacroNewsProvider, monkeypatch
    ):
        captured: dict[str, object] = {}

        async def mock_get(path: str, params: dict[str, str | int]):
            captured["path"] = path
            captured["params"] = params.copy()
            return []

        monkeypatch.setattr(macro_provider.client, "get", mock_get)

        await macro_provider.fetch_incremental(min_id=123)

        assert captured["path"] == "/news"
        assert captured["params"] == {"category": "general", "minId": 123}

    async def test_last_fetched_max_id_advances_only_on_newer_ids(
        self,
        macro_provider: FinnhubMacroNewsProvider,
        monkeypatch,
    ):
        fixed_now = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        module_path = macro_provider.__module__
        monkeypatch.setattr(f"{module_path}.datetime", MockDatetime)

        now_epoch = int(fixed_now.timestamp())
        articles_new = [
            {
                "id": 200,
                "headline": "A",
                "url": "https://example.com/a",
                "datetime": now_epoch,
                "related": "AAPL",
            },
            {
                "id": 201,
                "headline": "B",
                "url": "https://example.com/b",
                "datetime": now_epoch,
                "related": "MSFT",
            },
        ]
        articles_old = [
            {
                "id": 50,
                "headline": "Old",
                "url": "https://example.com/old",
                "datetime": now_epoch,
                "related": "AAPL",
            },
        ]

        macro_provider.client.get = AsyncMock(return_value=articles_new)
        await macro_provider.fetch_incremental(min_id=150)
        assert macro_provider.last_fetched_max_id == 201

        macro_provider.client.get = AsyncMock(return_value=articles_old)
        await macro_provider.fetch_incremental(min_id=150)
        assert macro_provider.last_fetched_max_id is None

    async def test_fetch_incremental_paginates_with_min_id(
        self, macro_provider: FinnhubMacroNewsProvider, monkeypatch
    ):
        fixed_now = datetime(2024, 2, 2, 12, 0, tzinfo=UTC)
        epoch = int(fixed_now.timestamp())
        real_datetime = datetime

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return real_datetime.fromtimestamp(ts, tz)

        module_path = macro_provider.__module__
        monkeypatch.setattr(f"{module_path}.datetime", MockDatetime)

        page_one = [
            {
                "id": 101,
                "headline": "A",
                "url": "https://example.com/a",
                "datetime": epoch,
                "related": "AAPL",
            },
            {
                "id": 102,
                "headline": "B",
                "url": "https://example.com/b",
                "datetime": epoch,
                "related": "MSFT",
            },
        ]
        page_two = [
            {
                "id": 103,
                "headline": "C",
                "url": "https://example.com/c",
                "datetime": epoch,
                "related": "AAPL",
            }
        ]
        responses = [page_one, page_two, []]
        captured_params: list[dict[str, object]] = []

        async def mock_get(path: str, params: dict[str, object]):
            captured_params.append(params.copy())
            return responses.pop(0)

        monkeypatch.setattr(macro_provider.client, "get", mock_get)

        result = await macro_provider.fetch_incremental(min_id=None)

        assert captured_params[0].get("minId") is None
        assert captured_params[1]["minId"] == 102
        assert macro_provider.last_fetched_max_id == 103
        assert len(result) == 3

    async def test_fetch_incremental_stops_at_bootstrap_cutoff(
        self, macro_provider: FinnhubMacroNewsProvider, monkeypatch
    ):
        fixed_now = datetime(2024, 2, 5, 12, 0, tzinfo=UTC)
        real_datetime = datetime

        class MockDatetime:
            @staticmethod
            def now(tz):  # pragma: no cover - shim
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):  # pragma: no cover - shim
                return real_datetime.fromtimestamp(ts, tz)

        module_path = macro_provider.__module__
        monkeypatch.setattr(f"{module_path}.datetime", MockDatetime)

        buffer_delta = timedelta(days=macro_provider.settings.macro_news_first_run_days)
        buffer_time = fixed_now - buffer_delta
        recent_epoch = int((buffer_time + timedelta(minutes=5)).timestamp())
        old_epoch = int((buffer_time - timedelta(minutes=5)).timestamp())
        articles = [
            {
                "id": 200,
                "headline": "New",
                "url": "https://example.com/new",
                "datetime": recent_epoch,
                "related": "AAPL",
            },
            {
                "id": 150,
                "headline": "Old",
                "url": "https://example.com/old",
                "datetime": old_epoch,
                "related": "AAPL",
            },
        ]

        mock_get = AsyncMock(return_value=articles)
        monkeypatch.setattr(macro_provider.client, "get", mock_get)

        result = await macro_provider.fetch_incremental(min_id=None)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert macro_provider.last_fetched_max_id == 200
        mock_get.assert_awaited_once()
