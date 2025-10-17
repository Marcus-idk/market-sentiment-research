"""Finnhub-specific macro news tests that complement contract coverage."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubMacroNewsProvider


@pytest.fixture
def macro_provider() -> FinnhubMacroNewsProvider:
    settings = FinnhubSettings(api_key="test_key")
    return FinnhubMacroNewsProvider(settings, ["AAPL", "MSFT"])


class TestFinnhubMacroProviderSpecific:
    """Tests for Finnhub-only behaviors not covered by macro contracts."""

    @pytest.mark.asyncio
    async def test_fetch_incremental_includes_min_id_param(self, macro_provider: FinnhubMacroNewsProvider):
        captured: dict[str, dict[str, str | int]] = {}

        async def mock_get(path: str, params: dict[str, str | int]):
            captured["path"] = path
            captured["params"] = params.copy()
            return []

        macro_provider.client.get = mock_get

        await macro_provider.fetch_incremental(min_id=123)

        assert captured["path"] == "/news"
        assert captured["params"] == {"category": "general", "minId": 123}

    @pytest.mark.asyncio
    async def test_last_fetched_max_id_advances_only_on_newer_ids(self, macro_provider: FinnhubMacroNewsProvider):
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        articles_new = [
            {"id": 200, "headline": "A", "url": "https://example.com/a", "datetime": now_epoch, "related": "AAPL"},
            {"id": 201, "headline": "B", "url": "https://example.com/b", "datetime": now_epoch, "related": "MSFT"},
        ]
        articles_old = [
            {"id": 50, "headline": "Old", "url": "https://example.com/old", "datetime": now_epoch, "related": "AAPL"},
        ]

        macro_provider.client.get = AsyncMock(return_value=articles_new)
        await macro_provider.fetch_incremental(min_id=150)
        assert macro_provider.last_fetched_max_id == 201

        macro_provider.client.get = AsyncMock(return_value=articles_old)
        await macro_provider.fetch_incremental(min_id=150)
        assert macro_provider.last_fetched_max_id is None