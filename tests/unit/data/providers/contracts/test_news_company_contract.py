"""Contract tests for company news providers."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data import DataSourceError, NewsItem


class TestNewsCompanyContract:
    """Shared behavior tests for company news providers."""

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        provider.client.validate_connection = AsyncMock(return_value=True)

        result = await provider.validate_connection()

        assert result is True
        provider.client.validate_connection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        provider.client.validate_connection = AsyncMock(side_effect=DataSourceError("boom"))

        with pytest.raises(DataSourceError):
            await provider.validate_connection()

    @pytest.mark.asyncio
    async def test_parses_valid_article(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        article = provider_spec_company.article_factory(
            headline="Tesla soars",
            url="https://example.com/tesla",
            epoch=now_epoch,
            source="Reuters",
            summary="Detailed content",
        )

        async def mock_get(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]] | dict[str, Any]:
            assert path == provider_spec_company.endpoint
            assert params and params[provider_spec_company.symbol_param_name] in provider_spec_company.default_symbols
            return provider_spec_company.wrap_response([article])

        provider.client.get = mock_get

        results = await provider.fetch_incremental()

        assert len(results) == 1
        item = results[0]
        assert isinstance(item, NewsItem)
        assert item.symbol in provider_spec_company.default_symbols
        assert item.headline == "Tesla soars"
        assert item.content == "Detailed content"
        assert item.source == "Reuters"
        assert item.published == datetime.fromtimestamp(now_epoch, tz=timezone.utc)

    @pytest.mark.asyncio
    async def test_skips_missing_headline(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        data = provider_spec_company.article_factory(headline="", url="https://example.com", epoch=1_705_320_000)

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([data])
        )

        results = await provider.fetch_incremental()

        assert results == []

    @pytest.mark.asyncio
    async def test_skips_missing_url(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        data = provider_spec_company.article_factory(headline="Headline", url="", epoch=1_705_320_000)

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([data])
        )

        results = await provider.fetch_incremental()

        assert results == []

    @pytest.mark.asyncio
    async def test_skips_invalid_timestamp(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        data = provider_spec_company.article_factory(epoch=0)

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([data])
        )

        results = await provider.fetch_incremental()

        assert results == []

    @pytest.mark.asyncio
    async def test_filters_articles_with_buffer(self, provider_spec_company, monkeypatch):
        provider = provider_spec_company.make_provider()

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

        buffer_epoch = int(datetime(2024, 1, 15, 9, 58, tzinfo=timezone.utc).timestamp())
        at_buffer = provider_spec_company.article_factory(epoch=buffer_epoch)
        inside_buffer = provider_spec_company.article_factory(epoch=buffer_epoch + 30)
        new_article = provider_spec_company.article_factory(epoch=buffer_epoch + 600)

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([at_buffer, inside_buffer, new_article])
        )

        since = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        results = await provider.fetch_incremental(since=since)

        assert [item.published for item in results] == [
            datetime.fromtimestamp(buffer_epoch + 30, tz=timezone.utc),
            datetime.fromtimestamp(buffer_epoch + 600, tz=timezone.utc),
        ]

    @pytest.mark.asyncio
    async def test_symbol_normalization_uppercases(self, provider_spec_company):
        provider = provider_spec_company.make_provider(symbols=["aapl", " tsla ", ""])

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([])
        )

        await provider.fetch_incremental()

        assert provider.symbols == ["AAPL", "TSLA"]

    @pytest.mark.asyncio
    async def test_summary_copied_to_content(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        article = provider_spec_company.article_factory(summary="Earnings beat expectations")

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([article])
        )

        results = await provider.fetch_incremental()

        assert len(results) == 1
        assert results[0].content == "Earnings beat expectations"

    @pytest.mark.asyncio
    async def test_per_symbol_error_isolation(self, provider_spec_company):
        provider = provider_spec_company.make_provider(symbols=["AAPL", "TSLA", "GOOG"])

        async def mock_get(path: str, params: dict[str, Any]):
            if params[provider_spec_company.symbol_param_name] == "TSLA":
                raise ValueError("TSLA broke")
            article = provider_spec_company.article_factory()
            return provider_spec_company.wrap_response([article])

        provider.client.get = mock_get

        results = await provider.fetch_incremental()

        assert len(results) == 2
        assert {item.symbol for item in results} == {"AAPL", "GOOG"}

    @pytest.mark.asyncio
    async def test_structural_error_raises(self, provider_spec_company):
        provider = provider_spec_company.make_provider()

        async def mock_get(path: str, params: dict[str, Any]) -> Any:
            return provider_spec_company.malformed(as_type=dict)

        provider.client.get = mock_get

        with pytest.raises(DataSourceError):
            await provider.fetch_incremental()

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self, provider_spec_company):
        provider = provider_spec_company.make_provider()
        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response([])
        )

        results = await provider.fetch_incremental()

        assert results == []

