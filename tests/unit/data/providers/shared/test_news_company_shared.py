"""Shared behavior tests for company news providers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data import DataSourceError, NewsEntry, NewsType

pytestmark = pytest.mark.asyncio


class TestNewsCompanyShared:
    """Shared behavior tests for company news providers."""

    async def test_validate_connection_success(self, provider_spec_company):
        """Test validate connection success."""
        provider = provider_spec_company.make_provider()
        provider.client.validate_connection = AsyncMock(return_value=True)

        result = await provider.validate_connection()

        assert result is True
        provider.client.validate_connection.assert_awaited_once()

    async def test_validate_connection_failure(self, provider_spec_company):
        """Test validate connection failure."""
        provider = provider_spec_company.make_provider()
        provider.client.validate_connection = AsyncMock(side_effect=DataSourceError("boom"))

        with pytest.raises(DataSourceError):
            await provider.validate_connection()

    async def test_parses_valid_article(self, provider_spec_company):
        """Test parses valid article."""
        provider = provider_spec_company.make_provider()
        now_epoch = int(datetime.now(UTC).timestamp())
        article = provider_spec_company.article_factory(
            headline="Tesla soars",
            url="https://example.com/tesla",
            epoch=now_epoch,
            source="Reuters",
            summary="Detailed content",
        )

        async def mock_get(
            path: str, params: dict[str, Any] | None = None
        ) -> list[dict[str, Any]] | dict[str, Any]:
            assert path == provider_spec_company.endpoint
            assert (
                params
                and params[provider_spec_company.symbol_param_name]
                in provider_spec_company.default_symbols
            )
            return provider_spec_company.wrap_response([article])

        provider.client.get = mock_get

        results = await provider.fetch_incremental()

        assert len(results) == 1
        item = results[0]
        assert isinstance(item, NewsEntry)
        assert item.symbol in provider_spec_company.default_symbols
        assert item.headline == "Tesla soars"
        assert item.content == "Detailed content"
        assert item.source == "Reuters"
        assert item.published == datetime.fromtimestamp(now_epoch, tz=UTC)
        assert item.news_type is NewsType.COMPANY_SPECIFIC
        assert item.is_important is True

    async def test_skips_missing_headline(self, provider_spec_company):
        """Test skips missing headline."""
        provider = provider_spec_company.make_provider()
        data = provider_spec_company.article_factory(
            headline="", url="https://example.com", epoch=1_705_320_000
        )

        provider.client.get = AsyncMock(return_value=provider_spec_company.wrap_response([data]))

        results = await provider.fetch_incremental()

        assert results == []

    async def test_skips_missing_url(self, provider_spec_company):
        """Test skips missing url."""
        provider = provider_spec_company.make_provider()
        data = provider_spec_company.article_factory(
            headline="Headline", url="", epoch=1_705_320_000
        )

        provider.client.get = AsyncMock(return_value=provider_spec_company.wrap_response([data]))

        results = await provider.fetch_incremental()

        assert results == []

    async def test_skips_invalid_timestamp(self, provider_spec_company):
        """Test skips invalid timestamp."""
        provider = provider_spec_company.make_provider()
        data = provider_spec_company.article_factory(epoch=0)

        provider.client.get = AsyncMock(return_value=provider_spec_company.wrap_response([data]))

        results = await provider.fetch_incremental()

        assert results == []

    async def test_filters_articles_with_buffer(self, provider_spec_company, monkeypatch):
        """Test filters articles with buffer."""
        provider = provider_spec_company.make_provider()

        class MockDatetime:
            @staticmethod
            def now(tz):
                return datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr(f"{provider.__module__}.datetime", MockDatetime)
        monkeypatch.setattr(f"{provider.__module__}.timezone", timezone)
        monkeypatch.setattr(f"{provider.__module__}.timedelta", timedelta)

        buffer_epoch = int(datetime(2024, 1, 15, 9, 58, tzinfo=UTC).timestamp())
        at_buffer = provider_spec_company.article_factory(epoch=buffer_epoch)
        inside_buffer = provider_spec_company.article_factory(epoch=buffer_epoch + 30)
        new_article = provider_spec_company.article_factory(epoch=buffer_epoch + 600)

        provider.client.get = AsyncMock(
            return_value=provider_spec_company.wrap_response(
                [at_buffer, inside_buffer, new_article]
            )
        )

        since = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        results = await provider.fetch_incremental(since=since)

        assert [item.published for item in results] == [
            datetime.fromtimestamp(buffer_epoch + 30, tz=UTC),
            datetime.fromtimestamp(buffer_epoch + 600, tz=UTC),
        ]
        assert all(item.is_important is True for item in results)

    async def test_date_window_params_with_since(self, provider_spec_company, monkeypatch):
        """Test date window params with since."""
        provider = provider_spec_company.make_provider()
        captured: list[tuple[str, dict[str, Any]]] = []
        fixed_now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        module_path = provider.__module__
        monkeypatch.setattr(f"{module_path}.datetime", MockDatetime)
        monkeypatch.setattr(f"{module_path}.timezone", timezone)
        monkeypatch.setattr(f"{module_path}.timedelta", timedelta)

        async def fake_get(path: str, params: dict[str, Any]):
            captured.append((path, dict(params)))
            return provider_spec_company.wrap_response([])

        provider.client.get = fake_get

        since = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        await provider.fetch_incremental(since=since)

        assert captured
        path, params = captured[0]
        assert path == provider_spec_company.endpoint

        overlap_delta = timedelta(minutes=provider.settings.company_news_overlap_minutes)

        expected_from = (since - overlap_delta).strftime("%Y-%m-%d")
        assert params["from"] == expected_from
        assert params["to"] == fixed_now.strftime("%Y-%m-%d")
        assert params["symbol"] in provider_spec_company.default_symbols

    async def test_date_window_params_without_since(self, provider_spec_company, monkeypatch):
        """Test date window params without since."""
        provider = provider_spec_company.make_provider()
        captured: list[tuple[str, dict[str, Any]]] = []
        fixed_now = datetime(2024, 2, 1, 12, 0, tzinfo=UTC)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        module_path = provider.__module__
        monkeypatch.setattr(f"{module_path}.datetime", MockDatetime)
        monkeypatch.setattr(f"{module_path}.timezone", timezone)
        monkeypatch.setattr(f"{module_path}.timedelta", timedelta)

        async def fake_get(path: str, params: dict[str, Any]):
            captured.append((path, dict(params)))
            return provider_spec_company.wrap_response([])

        provider.client.get = fake_get

        await provider.fetch_incremental(since=None)

        assert captured
        path, params = captured[0]
        assert path == provider_spec_company.endpoint

        bootstrap_delta = timedelta(days=provider.settings.company_news_first_run_days)

        expected_from = (fixed_now - bootstrap_delta).strftime("%Y-%m-%d")
        assert params["from"] == expected_from
        assert params["to"] == fixed_now.strftime("%Y-%m-%d")
        assert params["symbol"] in provider_spec_company.default_symbols

    async def test_symbol_normalization_uppercases(self, provider_spec_company):
        """Test symbol normalization uppercases."""
        provider = provider_spec_company.make_provider(symbols=["aapl", " tsla ", ""])

        provider.client.get = AsyncMock(return_value=provider_spec_company.wrap_response([]))

        await provider.fetch_incremental()

        assert provider.symbols == ["AAPL", "TSLA"]

    async def test_summary_copied_to_content(self, provider_spec_company):
        """Test summary copied to content."""
        provider = provider_spec_company.make_provider()
        article = provider_spec_company.article_factory(summary="Earnings beat expectations")

        provider.client.get = AsyncMock(return_value=provider_spec_company.wrap_response([article]))

        results = await provider.fetch_incremental()

        assert len(results) == 1
        assert results[0].content == "Earnings beat expectations"
        assert results[0].is_important is True

    async def test_per_symbol_error_isolation(self, provider_spec_company):
        """Test per symbol error isolation."""
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
        assert all(item.is_important is True for item in results)

    async def test_structural_error_logs_warning_and_skips(self, provider_spec_company, caplog):
        """Test structural error logs warning and skips."""
        provider = provider_spec_company.make_provider()

        async def mock_get(path: str, params: dict[str, Any]) -> Any:
            return provider_spec_company.malformed(as_type=dict)

        provider.client.get = mock_get

        caplog.set_level("WARNING", logger=provider.__module__)

        results = await provider.fetch_incremental()

        assert results == []
        assert any("instead of list" in message for message in caplog.messages)

    async def test_empty_response_returns_empty_list(self, provider_spec_company):
        """Test empty response returns empty list."""
        provider = provider_spec_company.make_provider()
        provider.client.get = AsyncMock(return_value=provider_spec_company.wrap_response([]))

        results = await provider.fetch_incremental()

        assert results == []

    async def test_symbol_since_map_takes_precedence(self, provider_spec_company):
        """Test symbol since map takes precedence."""
        provider = provider_spec_company.make_provider(symbols=["AAPL", "TSLA"])

        if not hasattr(provider, "_resolve_symbol_cursor"):
            pytest.skip("provider does not expose symbol cursor helper")

        global_since = datetime(2024, 1, 10, 12, 0, tzinfo=UTC)
        symbol_since = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)

        result_aapl = provider._resolve_symbol_cursor("AAPL", {"AAPL": symbol_since}, global_since)
        result_tsla = provider._resolve_symbol_cursor("TSLA", {"AAPL": symbol_since}, global_since)

        assert result_aapl == symbol_since
        assert result_tsla == global_since

    async def test_symbol_cursor_falls_back_to_global_or_none(self, provider_spec_company):
        """Test symbol cursor falls back to global or none."""
        provider = provider_spec_company.make_provider(symbols=["AAPL"])

        if not hasattr(provider, "_resolve_symbol_cursor"):
            pytest.skip("provider does not expose symbol cursor helper")

        global_since = datetime(2024, 1, 8, 15, 0, tzinfo=UTC)

        result_with_global = provider._resolve_symbol_cursor("AAPL", {}, global_since)
        result_without_global = provider._resolve_symbol_cursor("AAPL", None, None)

        assert result_with_global == global_since
        assert result_without_global is None
