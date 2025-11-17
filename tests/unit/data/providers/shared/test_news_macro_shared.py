"""Shared behavior tests for macro news providers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data import DataSourceError, NewsEntry, NewsType

pytestmark = pytest.mark.asyncio


class TestNewsMacroShared:
    """Shared behavior tests for macro news providers."""

    async def test_validate_connection_success(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        provider.client.validate_connection = AsyncMock(return_value=True)

        result = await provider.validate_connection()

        assert result is True
        provider.client.validate_connection.assert_awaited_once()

    async def test_validate_connection_failure(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        provider.client.validate_connection = AsyncMock(side_effect=DataSourceError("fail"))

        with pytest.raises(DataSourceError):
            await provider.validate_connection()

    async def test_maps_related_symbols(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=["AAPL", "MSFT", "TSLA"])
        now_epoch = int(datetime.now(UTC).timestamp())
        article = provider_spec_macro.article_factory(
            symbols="AAPL,MSFT,GOOG",
            epoch=now_epoch,
        )

        provider.client.get = AsyncMock(return_value=provider_spec_macro.wrap_response([article]))

        results = await provider.fetch_incremental()

        assert all(isinstance(item, NewsEntry) for item in results)
        assert {item.symbol for item in results} == {"AAPL", "MSFT"}
        assert {item.news_type for item in results} == {NewsType.MACRO}
        assert all(item.is_important is None for item in results)

    async def test_falls_back_to_market_when_no_related(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=["AAPL", "MSFT"])
        now_epoch = int(datetime.now(UTC).timestamp())
        article = provider_spec_macro.article_factory(symbols="", epoch=now_epoch)

        provider.client.get = AsyncMock(return_value=provider_spec_macro.wrap_response([article]))

        results = await provider.fetch_incremental()

        assert len(results) == 1
        fallback = results[0]
        assert isinstance(fallback, NewsEntry)
        assert fallback.symbol == "MARKET"
        assert fallback.news_type is NewsType.MACRO
        assert fallback.is_important is None

    async def test_filters_buffer_time_when_bootstrap(self, provider_spec_macro, monkeypatch):
        provider = provider_spec_macro.make_provider()

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

        bootstrap_delta = timedelta(days=provider.settings.macro_news_first_run_days)
        buffer_anchor = datetime(2024, 1, 15, 10, 0, tzinfo=UTC) - bootstrap_delta
        buffer_epoch = int(buffer_anchor.timestamp())
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
        entry = results[0]
        assert entry.published == datetime.fromtimestamp(inside_epoch, tz=UTC)
        assert entry.news_type is NewsType.MACRO
        assert entry.is_important is None

    async def test_invalid_articles_are_skipped(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        now_epoch = int(datetime.now(UTC).timestamp())
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
        entry = results[0]
        assert entry.headline == good_article[headline_field]
        assert entry.news_type is NewsType.MACRO
        assert entry.is_important is None

    async def test_structural_error_raises(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()

        async def mock_get(path: str, params: dict[str, Any]) -> Any:
            return provider_spec_macro.malformed(as_type=dict)

        provider.client.get = mock_get

        with pytest.raises(DataSourceError):
            await provider.fetch_incremental()

    async def test_empty_watchlist_falls_back_to_market(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=[])
        now_epoch = int(datetime.now(UTC).timestamp())
        article = provider_spec_macro.article_factory(symbols="GOOG", epoch=now_epoch)

        provider.client.get = AsyncMock(return_value=provider_spec_macro.wrap_response([article]))

        results = await provider.fetch_incremental()

        assert len(results) == 1
        fallback = results[0]
        assert isinstance(fallback, NewsEntry)
        assert fallback.symbol == "MARKET"
        assert fallback.news_type is NewsType.MACRO
        assert fallback.is_important is None

    async def test_structural_error_non_dict_response(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider()
        provider.client.get = AsyncMock(return_value="unexpected-type")

        with pytest.raises(DataSourceError):
            if "finnhub" in provider_spec_macro.name:
                await provider.fetch_incremental(min_id=None)
            else:
                await provider.fetch_incremental(since=None)

    async def test_parse_exception_skips_article_and_continues(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=["AAPL"])
        malformed = provider_spec_macro.article_factory(headline=None)
        valid = provider_spec_macro.article_factory(symbols="AAPL")
        payload = provider_spec_macro.wrap_response([malformed, valid])
        provider.client.get = AsyncMock(return_value=payload)

        if "finnhub" in provider_spec_macro.name:
            results = await provider.fetch_incremental(min_id=None)
            headline_field = "headline"
        else:
            results = await provider.fetch_incremental(since=None)
            headline_field = "title"

        assert len(results) == 1
        entry = results[0]
        assert entry.headline == valid[headline_field]
        assert entry.news_type is NewsType.MACRO
        assert entry.is_important is None

    async def test_invalid_timestamp_skips_article(self, provider_spec_macro, monkeypatch):
        provider = provider_spec_macro.make_provider(symbols=["AAPL"])
        article = provider_spec_macro.article_factory(symbols="AAPL")

        if "finnhub" in provider_spec_macro.name:
            article["datetime"] = 1234567890

            class BadDatetime:
                @staticmethod
                def now(tz):
                    return datetime.now(tz)

                @staticmethod
                def fromtimestamp(ts, tz):
                    raise ValueError("bad timestamp")

            monkeypatch.setattr(
                "data.providers.finnhub.finnhub_macro_news.datetime",
                BadDatetime,
            )
        else:
            article["published_utc"] = "not-a-timestamp"

        provider.client.get = AsyncMock(return_value=provider_spec_macro.wrap_response([article]))

        if "finnhub" in provider_spec_macro.name:
            results = await provider.fetch_incremental(min_id=None)
        else:
            results = await provider.fetch_incremental(since=None)

        assert results == []

    async def test_newsitem_validation_failure_skips_article(self, provider_spec_macro):
        provider = provider_spec_macro.make_provider(symbols=["AAPL"])
        article = provider_spec_macro.article_factory(symbols="AAPL")

        if "finnhub" in provider_spec_macro.name:
            article["url"] = "ftp://invalid"
        else:
            article["article_url"] = "ftp://invalid"

        provider.client.get = AsyncMock(return_value=provider_spec_macro.wrap_response([article]))

        if "finnhub" in provider_spec_macro.name:
            results = await provider.fetch_incremental(min_id=None)
        else:
            results = await provider.fetch_incremental(since=None)

        assert results == []

    async def test_newsentry_validation_failure_skips_symbol(
        self, provider_spec_macro, monkeypatch
    ):
        provider = provider_spec_macro.make_provider(symbols=["AAPL"])
        article = provider_spec_macro.article_factory(symbols="AAPL")

        if "finnhub" in provider_spec_macro.name:
            monkeypatch.setattr(
                provider,
                "_extract_symbols_from_related",
                lambda related: ["", "AAPL"],
            )
            fetch_kwargs = {"min_id": None}
        else:
            monkeypatch.setattr(
                provider,
                "_extract_symbols_from_tickers",
                lambda tickers: ["", "AAPL"],
            )
            fetch_kwargs = {"since": None}

        provider.client.get = AsyncMock(return_value=provider_spec_macro.wrap_response([article]))

        results = await provider.fetch_incremental(**fetch_kwargs)

        assert len(results) == 1
        entry = results[0]
        assert entry.symbol == "AAPL"
        assert entry.news_type is NewsType.MACRO
        assert entry.is_important is None
