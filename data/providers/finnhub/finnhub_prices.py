"""Price provider implementation."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data.base import PriceDataSource
from data.models import PriceData
from utils.market_sessions import classify_us_session
from .finnhub_client import FinnhubClient


logger = logging.getLogger(__name__)


class FinnhubPriceProvider(PriceDataSource):
    """Fetches real-time quotes from Finnhub's /quote endpoint."""

    def __init__(self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub") -> None:
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(self, since: datetime | None = None) -> list[PriceData]:
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
            except Exception as exc:  # noqa: BLE001
                logger.warning("Price quote fetch failed for %s: %s", symbol, exc)
                continue

        return price_data

    def _parse_quote(self, quote: dict[str, Any], symbol: str) -> PriceData | None:
        current_price = quote.get("c", 0)
        if current_price <= 0:
            return None

        try:
            price = Decimal(str(current_price))
        except (ValueError, TypeError) as exc:
            logger.debug("Invalid quote price for %s: %r (%s) - skipping", symbol, current_price, exc)
            return None

        quote_timestamp = quote.get("t", 0)
        if quote_timestamp > 0:
            try:
                timestamp = datetime.fromtimestamp(quote_timestamp, tz=timezone.utc)
            except (ValueError, OSError) as exc:
                logger.debug("Invalid quote timestamp for %s: %r (%s) - using now()", symbol, quote_timestamp, exc)
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        try:
            return PriceData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=None,
                session=classify_us_session(timestamp),
            )
        except ValueError as exc:  # pragma: no cover
            logger.debug("PriceData validation failed for %s (price=%s): %s", symbol, price, exc)
            return None

