"""Contract tests for macro news providers."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data import DataSourceError


class TestNewsMacroContract:
    """Shared behavior tests for macro news providers."""

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        provider.client.validate_connection = AsyncMock(return_value=True)

        result = await provider.validate_connection()

        assert result is True
        provider.client.validate_connection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        provider.client.validate_connection = AsyncMock(side_effect=DataSourceError("fail"))

        with pytest.raises(DataSourceError):
            await provider.validate_connection()

    @pytest.mark.asyncio
    async def test_maps_related_symbols(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=["AAPL", "MSFT", "TSLA"])
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        article = provider_spec_macro.article_factory(
            symbols="AAPL,MSFT,GOOG",
            epoch=now_epoch,
        )

        provider.client.get = AsyncMock(
            return_value=provider_spec_macro.wrap_response([article])
        )

        results = await provider.fetch_incremental()

        assert {item.symbol for item in results} == {"AAPL", "MSFT"}

    @pytest.mark.asyncio
    async def test_falls_back_to_all_when_no_related(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=["AAPL", "MSFT"])
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        article = provider_spec_macro.article_factory(symbols="", epoch=now_epoch)

        provider.client.get = AsyncMock(
            return_value=provider_spec_macro.wrap_response([article])
        )

        results = await provider.fetch_incremental()

        assert len(results) == 1
        assert results[0].symbol == "ALL"

    @pytest.mark.asyncio
    async def test_filters_buffer_time_when_bootstrap(self, provider_spec_macro, monkeypatch):
        provider = provider_spec_macro.make_provider()

        class MockDatetime:
            @staticmethod
            def now(tz):
                return datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr(f"{provider.__module__}.datetime", MockDatetime)
        monkeypatch.setattr(f"{provider.__module__}.timezone", timezone)
        monkeypatch.setattr(f"{provider.__module__}.timedelta", timedelta)

        buffer_epoch = int(datetime(2024, 1, 13, 10, 0, tzinfo=timezone.utc).timestamp())
        inside_epoch = buffer_epoch + 60
        article_old = provider_spec_macro.article_factory(epoch=buffer_epoch)
        article_new = provider_spec_macro.article_factory(epoch=inside_epoch)

        provider.client.get = AsyncMock(
            return_value=provider_spec_macro.wrap_response([article_old, article_new])
        )

        if "finnhub" in provider_spec_macro.name:
            results = await provider.fetch_incremental(min_id=None)
        else:
            results = await provider.fetch_incremental(since=None)

        assert len(results) == 1
        assert results[0].published == datetime.fromtimestamp(inside_epoch, tz=timezone.utc)

    @pytest.mark.asyncio
    async def test_invalid_articles_are_skipped(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        bad_headline = provider_spec_macro.article_factory(headline="", epoch=now_epoch)
        bad_url = provider_spec_macro.article_factory(url="", epoch=now_epoch)
        bad_timestamp = provider_spec_macro.article_factory(epoch=0)
        good_article = provider_spec_macro.article_factory(epoch=now_epoch)

        provider.client.get = AsyncMock(
            return_value=provider_spec_macro.wrap_response(
                [bad_headline, bad_url, bad_timestamp, good_article]
            )
        )

        results = await provider.fetch_incremental()

        assert len(results) == 1
        # Need to check the right field name based on provider
        headline_field = "title" if "title" in good_article else "headline"
        assert results[0].headline == good_article[headline_field]

    @pytest.mark.asyncio
    async def test_structural_error_raises(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()

        async def mock_get(path: str, params: dict[str, Any]) -> Any:
            return provider_spec_macro.malformed(as_type=dict)

        provider.client.get = mock_get

        with pytest.raises(DataSourceError):
            await provider.fetch_incremental()

    @pytest.mark.asyncio
    async def test_empty_watchlist_falls_back_to_all(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=[])
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        article = provider_spec_macro.article_factory(symbols="GOOG", epoch=now_epoch)

        provider.client.get = AsyncMock(
            return_value=provider_spec_macro.wrap_response([article])
        )

        results = await provider.fetch_incremental()

        assert len(results) == 1
        assert results[0].symbol == "ALL"
