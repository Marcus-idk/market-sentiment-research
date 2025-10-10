"""Price provider implementation."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data import PriceDataSource, DataSourceError
from data.models import PriceData
from utils.market_sessions import classify_us_session
from utils.retry import RetryableError
from data.providers.finnhub.finnhub_client import FinnhubClient


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
            except (
                RetryableError,
                DataSourceError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                logger.warning(f"Price quote fetch failed for {symbol}: {exc}")
                continue
            except Exception as exc:  # pragma: no cover - unexpected
                logger.exception(f"Unexpected error fetching price for {symbol}: {exc}")
                continue

        return price_data

    def _parse_quote(self, quote: dict[str, Any], symbol: str) -> PriceData | None:
        current_price = quote.get("c", 0)
        if current_price <= 0:
            return None

        try:
            price = Decimal(str(current_price))
        except (ValueError, TypeError) as exc:
            logger.debug(
                f"Invalid quote price for {symbol}: {current_price!r} ({exc}) - skipping"
            )
            return None

        quote_timestamp = quote.get("t", 0)
        if quote_timestamp > 0:
            try:
                timestamp = datetime.fromtimestamp(quote_timestamp, tz=timezone.utc)
            except (ValueError, OSError) as exc:
                logger.debug(
                    f"Invalid quote timestamp for {symbol}: {quote_timestamp!r} ({exc}) - using now()"
                )
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
            logger.debug(
                f"PriceData validation failed for {symbol} (price={price}): {exc}"
            )
            return None

