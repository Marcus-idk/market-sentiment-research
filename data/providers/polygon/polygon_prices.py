"""Polygon.io price provider implementation."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from config.providers.polygon import PolygonSettings
from data import PriceDataSource
from data.models import PriceData
from data.providers.polygon.polygon_client import PolygonClient
from utils.market_sessions import classify_us_session


logger = logging.getLogger(__name__)


class PolygonPriceProvider(PriceDataSource):
    """Fetches real-time price snapshots from Polygon.io.

    Rate Limits:
        Free tier: ~5 calls/min. Each poll cycle makes one call per symbol.
        For 5-min polling, this supports up to ~25 symbols before hitting rate limits.
        Consider rotating symbols or only enabling Polygon for smaller watchlists.
    """

    def __init__(
        self, settings: PolygonSettings, symbols: list[str], source_name: str = "Polygon"
    ) -> None:
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = PolygonClient(settings)

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(self, since: datetime | None = None) -> list[PriceData]:
        if not self.symbols:
            return []

        price_data: list[PriceData] = []

        for symbol in self.symbols:
            try:
                response = await self.client.get(
                    f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
                )

                if not isinstance(response, dict):
                    continue

                ticker_data = response.get("ticker")
                if not ticker_data or not isinstance(ticker_data, dict):
                    continue

                price_item = self._parse_snapshot(ticker_data, symbol)
                if price_item:
                    price_data.append(price_item)
            except Exception as exc:
                logger.warning(f"Price snapshot fetch failed for {symbol}: {exc}")
                continue

        return price_data

    def _parse_snapshot(self, ticker: dict[str, Any], symbol: str) -> PriceData | None:
        """Parse Polygon snapshot response into PriceData."""
        # Prefer lastTrade.p
        price_value = None
        last_trade = ticker.get("lastTrade")
        if last_trade and isinstance(last_trade, dict):
            trade_price = last_trade.get("p", 0)
            if trade_price > 0:
                price_value = trade_price

        # Fallback to quote midpoint
        if price_value is None:
            last_quote = ticker.get("lastQuote")
            if last_quote and isinstance(last_quote, dict):
                ask = last_quote.get("P", 0)  # Ask price (uppercase P)
                bid = last_quote.get("p", 0)  # Bid price (lowercase p)
                if ask > 0 and bid > 0:
                    price_value = (ask + bid) / 2

        # Skip if no valid price
        if price_value is None or price_value <= 0:
            return None

        # Convert to Decimal
        try:
            price = Decimal(str(price_value))
        except (ValueError, TypeError) as exc:
            logger.debug(
                f"Invalid price for {symbol}: {price_value!r} ({exc}) - skipping"
            )
            return None

        # Extract volume from day data
        volume = None
        day_data = ticker.get("day")
        if day_data and isinstance(day_data, dict):
            day_volume = day_data.get("v")
            if day_volume and day_volume > 0:
                try:
                    volume = int(day_volume)
                except (ValueError, TypeError):
                    pass

        # Parse timestamp (nanoseconds)
        timestamp_ns = ticker.get("updated", 0)
        if timestamp_ns > 0:
            try:
                # Convert nanoseconds to seconds
                timestamp = datetime.fromtimestamp(
                    timestamp_ns / 1e9, tz=timezone.utc
                )
            except (ValueError, OSError) as exc:
                logger.debug(
                    f"Invalid timestamp for {symbol}: {timestamp_ns!r} ({exc}) - using now()"
                )
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        # Create PriceData
        try:
            return PriceData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=volume,
                session=classify_us_session(timestamp),
            )
        except ValueError as exc:
            logger.debug(f"PriceData validation failed for {symbol} (price={price}): {exc}")
            return None
