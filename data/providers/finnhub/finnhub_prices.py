"""Price provider implementation."""

import logging
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal, InvalidOperation
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data import DataSourceError, PriceDataSource
from data.models import PriceData
from data.providers.finnhub.finnhub_client import FinnhubClient
from utils.datetime_utils import epoch_seconds_to_utc_datetime
from utils.market_sessions import classify_us_session
from utils.retry import RetryableError
from utils.symbols import normalize_symbol_list

logger = logging.getLogger(__name__)


class FinnhubPriceProvider(PriceDataSource):
    """Fetches real-time quotes from Finnhub's /quote endpoint."""

    def __init__(
        self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub"
    ) -> None:
        """Initialize the Finnhub price provider."""
        super().__init__(source_name)
        self.symbols = normalize_symbol_list(symbols)
        self.client = FinnhubClient(settings)

    async def validate_connection(self) -> bool:
        """Return True when the Finnhub API is reachable."""
        return await self.client.validate_connection()

    async def fetch_incremental(self) -> list[PriceData]:
        """Fetch latest quotes for configured symbols."""
        if not self.symbols:
            return []

        price_data: list[PriceData] = []

        for symbol in self.symbols:
            try:
                quote = await self.client.get("/quote", {"symbol": symbol})

                if not isinstance(quote, dict):
                    raise DataSourceError(
                        f"Finnhub /quote expected dict for {symbol}, got {type(quote).__name__}"
                    )

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
                logger.warning("Price quote fetch failed for %s: %s", symbol, exc)
                continue

        return price_data

    def _parse_quote(self, quote: dict[str, Any], symbol: str) -> PriceData | None:
        """Convert Finnhub /quote payload into PriceData.

        Notes:
            Returns None when required fields are missing/invalid or price is non-positive.
        """
        raw_price = quote.get("c")
        if raw_price is None:
            logger.debug("Skipping quote for %s due to missing 'c' price field", symbol)
            return None

        try:
            price = Decimal(str(raw_price))
        except (ValueError, TypeError, InvalidOperation) as exc:
            logger.debug("Invalid quote price for %s: %r (%s) - skipping", symbol, raw_price, exc)
            return None

        if price <= 0:
            logger.debug(
                "Finnhub /quote returned non-positive price for %s: %r - skipping",
                symbol,
                price,
            )
            return None

        quote_timestamp = quote.get("t")
        if isinstance(quote_timestamp, (int, float)) and quote_timestamp > 0:
            try:
                timestamp = epoch_seconds_to_utc_datetime(quote_timestamp)
            except (ValueError, OSError, OverflowError) as exc:
                logger.debug(
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
            logger.debug("PriceData validation failed for %s (price=%s): %s", symbol, price, exc)
            return None
