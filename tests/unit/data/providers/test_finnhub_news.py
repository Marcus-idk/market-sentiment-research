"""Finnhub-specific company news tests (contract coverage handled elsewhere)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import pytest

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubNewsProvider


class TestFinnhubNewsProviderSpecific:
    """Tests for Finnhub-only behaviors not covered by company news contracts."""

    @pytest.mark.asyncio
    async def test_fetch_incremental_with_no_symbols_returns_empty_list(self):
        provider = FinnhubNewsProvider(FinnhubSettings(api_key="test_key"), [])

        result = await provider.fetch_incremental()

        assert result == []

    @pytest.mark.asyncio
    async def test_date_window_with_since(self, monkeypatch):
        """Test Finnhub-specific 'from' and 'to' date parameters."""
        provider = FinnhubNewsProvider(FinnhubSettings(api_key="test_key"), ["AAPL"])
        captured: dict[str, Any] = {}

        class MockDatetime:
            @staticmethod
            def now(tz):
                return datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr("data.providers.finnhub.finnhub_news.datetime", MockDatetime)
        monkeypatch.setattr("data.providers.finnhub.finnhub_news.timezone", timezone)
        monkeypatch.setattr("data.providers.finnhub.finnhub_news.timedelta", timedelta)

        async def mock_get(path: str, params: dict[str, Any]):
            captured["path"] = path
            captured["params"] = params
            return []

        provider.client.get = mock_get

        since = datetime(2024, 1, 13, 5, 0, tzinfo=timezone.utc)
        await provider.fetch_incremental(since=since)

        assert captured["path"] == "/company-news"
        assert captured["params"]["from"] == "2024-01-13"
        assert captured["params"]["to"] == "2024-01-15"
        assert captured["params"]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_date_window_without_since(self, monkeypatch):
        """Test Finnhub-specific 'from' and 'to' date parameters with no since."""
        provider = FinnhubNewsProvider(FinnhubSettings(api_key="test_key"), ["AAPL"])
        captured: dict[str, Any] = {}

        class MockDatetime:
            @staticmethod
            def now(tz):
                return datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr("data.providers.finnhub.finnhub_news.datetime", MockDatetime)
        monkeypatch.setattr("data.providers.finnhub.finnhub_news.timezone", timezone)
        monkeypatch.setattr("data.providers.finnhub.finnhub_news.timedelta", timedelta)

        async def mock_get(path: str, params: dict[str, Any]):
            captured["path"] = path
            captured["params"] = params
            return []

        provider.client.get = mock_get

        await provider.fetch_incremental(since=None)

        assert captured["path"] == "/company-news"
        assert captured["params"]["from"] == "2024-01-13"
        assert captured["params"]["to"] == "2024-01-15"
        assert captured["params"]["symbol"] == "AAPL"
