"""Shared behavior tests for price data providers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data import DataSourceError, PriceData

pytestmark = pytest.mark.asyncio

class TestPricesShared:
    """Shared behavior tests for price providers."""

    async def test_validate_connection_success(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider()
        provider.client.validate_connection = AsyncMock(return_value=True)

        result = await provider.validate_connection()

        assert result is True
        provider.client.validate_connection.assert_awaited_once()

    async def test_validate_connection_failure(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider()
        provider.client.validate_connection = AsyncMock(side_effect=DataSourceError("broken"))

        with pytest.raises(DataSourceError):
            await provider.validate_connection()

    async def test_decimal_conversion(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        quote = provider_spec_prices.quote(price=123.4567, timestamp=1_705_320_000)
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert len(results) == 1
        item = results[0]
        assert isinstance(item, PriceData)
        assert item.price == Decimal("123.4567")

    async def test_classifies_session(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        ts = datetime(2024, 1, 17, 15, 0, tzinfo=timezone.utc)
        quote = provider_spec_prices.quote(price=150.0, timestamp=int(ts.timestamp()))
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert results[0].session.name == "REG"

    async def test_rejects_negative_price(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        quote = provider_spec_prices.quote(price=-1, timestamp=1_705_320_000)
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert results == []

    async def test_rejects_zero_price(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        quote = provider_spec_prices.quote(price=0, timestamp=1_705_320_000)
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert results == []

    async def test_rejects_string_price(self, provider_spec_prices, caplog):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        quote = provider_spec_prices.quote(price="invalid", timestamp=1_705_320_000)
        provider.client.get = AsyncMock(return_value=quote)
        caplog.set_level("DEBUG", logger=provider.__module__)

        results = await provider.fetch_incremental()

        assert results == []
        assert any("invalid" in message for message in caplog.messages)

    async def test_rejects_missing_price_field(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        quote = provider_spec_prices.quote(price=None, timestamp=1_705_320_000)
        if "c" in quote:
            quote.pop("c")
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert results == []

    async def test_timestamp_fallback_when_missing(self, provider_spec_prices, monkeypatch):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        fixed_now = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr(f"{provider.__module__}.datetime", MockDatetime)
        quote = provider_spec_prices.quote(price=150.0, timestamp=None)
        if "t" in quote:
            quote.pop("t")
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert results[0].timestamp == fixed_now

    async def test_timestamp_fallback_when_invalid(self, provider_spec_prices, monkeypatch):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        fixed_now = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                if ts == -9999999999:
                    raise OSError("invalid")
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr(f"{provider.__module__}.datetime", MockDatetime)
        quote = provider_spec_prices.quote(price=150.0, timestamp=-9999999999)
        provider.client.get = AsyncMock(return_value=quote)

        results = await provider.fetch_incremental()

        assert results[0].timestamp == fixed_now

    async def test_error_isolation_per_symbol(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL", "FAIL", "TSLA"])

        async def mock_get(path: str, params: dict[str, Any]):
            if params["symbol"] == "FAIL":
                raise DataSourceError("fail")
            return provider_spec_prices.quote(price=200.0, timestamp=1_705_320_000)

        provider.client.get = mock_get

        results = await provider.fetch_incremental()

        assert {item.symbol for item in results} == {"AAPL", "TSLA"}

    async def test_non_dict_quote_skipped(self, provider_spec_prices):
        provider = provider_spec_prices.make_provider(symbols=["AAPL"])
        provider.client.get = AsyncMock(return_value=[provider_spec_prices.malformed(as_type=str)])

        results = await provider.fetch_incremental()

        assert results == []
