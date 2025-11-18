"""Price provider implementation."""

import logging
from datetime import (
    UTC,
    datetime,
    timezone,  # noqa: F401 - used by tests via monkeypatch
)
from decimal import Decimal, InvalidOperation
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data import DataSourceError, PriceDataSource
from data.models import PriceData
from data.providers.finnhub.finnhub_client import FinnhubClient
from utils.market_sessions import classify_us_session
from utils.retry import RetryableError

logger = logging.getLogger(__name__)


class FinnhubPriceProvider(PriceDataSource):
    """Fetches real-time quotes from Finnhub's /quote endpoint."""

    def __init__(
        self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub"
    ) -> None:
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(self) -> list[PriceData]:
        if not self.symbols:
            return []

        price_data: list[PriceData] = []

        for symbol in self.symbols:
            try:
                quote = await self.client.get("/quote", {"symbol": symbol})

                if not isinstance(quote, dict):
                    continue

                price_item = self._parse_quote(quote, symbol)
                if price_item:
                    price_data.append(price_item)
            except (
                RetryableError,
                DataSourceError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                logger.warning(f"Price quote fetch failed for {symbol}: {exc}")
                continue

        return price_data

    def _parse_quote(self, quote: dict[str, Any], symbol: str) -> PriceData | None:
        raw_price = quote.get("c")
        if raw_price is None:
            return None

        try:
            price = Decimal(str(raw_price))
        except (ValueError, TypeError, InvalidOperation) as exc:
            logger.debug(f"Invalid quote price for {symbol}: {raw_price!r} ({exc}) - skipping")
            return None

        if price <= 0:
            logger.warning(
                f"Finnhub /quote returned non-positive price for {symbol}: {price!r} - skipping"
            )
            return None

        quote_timestamp = quote.get("t", 0)
        if quote_timestamp > 0:
            try:
                timestamp = datetime.fromtimestamp(quote_timestamp, tz=UTC)
            except (ValueError, OSError) as exc:
                logger.warning(
                    "Invalid quote timestamp for %s: %r (%s) - using now()",
                    symbol,
                    quote_timestamp,
                    exc,
                )
                timestamp = datetime.now(UTC)
        else:
            timestamp = datetime.now(UTC)

        try:
            return PriceData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=None,
                session=classify_us_session(timestamp),
            )
        except ValueError as exc:
            logger.debug(f"PriceData validation failed for {symbol} (price={price}): {exc}")
            return None
