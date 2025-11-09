"""Finnhub-specific macro news tests that complement contract coverage."""

from __future__ import annotations

from datetime import UTC, datetime
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
