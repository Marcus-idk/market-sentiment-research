"""
Data poller for continuous market data collection.

Orchestrates fetching from configured providers at regular intervals,
storing results in SQLite, managing watermarks for incremental fetching,
and deduplicating prices from multiple providers.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import TypedDict, cast

from analysis.urgency_detector import detect_urgency
from data import DataSourceError, NewsDataSource, PriceDataSource
from data.models import NewsEntry, PriceData
from data.providers.finnhub import FinnhubMacroNewsProvider
from data.storage import (
    get_last_macro_min_id,
    get_last_news_time,
    set_last_macro_min_id,
    set_last_news_time,
    store_news_items,
    store_price_data,
)
from llm.base import LLMError
from utils.retry import RetryableError

logger = logging.getLogger(__name__)


class DataBatch(TypedDict):
    """Data fetched from all providers in one cycle."""

    company_news: list[NewsEntry]
    macro_news: list[NewsEntry]
    prices: dict[PriceDataSource, dict[str, PriceData]]  # {provider: {symbol: PriceData}}
    errors: list[str]


class PollStats(TypedDict):
    """Statistics from one polling cycle."""

    news: int
    prices: int
    errors: list[str]


class DataPoller:
    """
    Polls configured providers for news and price data at regular intervals.

    Handles watermark-based incremental fetching, partial failures,
    price deduplication across providers, and graceful shutdown.
    """

    def __init__(
        self,
        db_path: str,
        news_providers: list[NewsDataSource],
        price_providers: list[PriceDataSource],
        poll_interval: int,
    ) -> None:
        """
        Initialize the data poller.

        Args:
            db_path: Path to SQLite database
            news_providers: List of news provider instances
            price_providers: List of price provider instances
            poll_interval: Polling interval in seconds
        """
        self.db_path = db_path
        self.news_providers = news_providers
        self.price_providers = price_providers
        self.poll_interval = poll_interval
        self.running = False
        self._stop_event = asyncio.Event()

        # Track macro providers that use ID-based watermarks (currently Finnhub macro endpoint)
        self._finnhub_macro_providers: set[NewsDataSource] = {
            provider
            for provider in news_providers
            if isinstance(provider, FinnhubMacroNewsProvider)
        }

    async def _read_watermarks(self) -> tuple[datetime | None, int | None]:
        """Read persisted watermarks on a background thread."""
        last_news_time = await asyncio.to_thread(get_last_news_time, self.db_path)
        last_macro_min_id = await asyncio.to_thread(get_last_macro_min_id, self.db_path)
        return last_news_time, last_macro_min_id

    async def _fetch_all_data(
        self,
        last_news_time: datetime | None,
        last_macro_min_id: int | None,
    ) -> DataBatch:
        """
        Fetch data from all providers concurrently.

        Returns:
            DataBatch with company_news, macro_news, prices, and errors
        """
        # Separate results by provider type
        company_news: list[NewsEntry] = []
        macro_news: list[NewsEntry] = []
        prices_by_provider: dict[PriceDataSource, dict[str, PriceData]] = {}
        errors = []

        # Start both news and price fetches concurrently (don't await yet)
        news_tasks = []
        for provider in self.news_providers:
            if provider in self._finnhub_macro_providers:
                news_tasks.append(provider.fetch_incremental(min_id=last_macro_min_id))
            else:
                news_tasks.append(provider.fetch_incremental(since=last_news_time))

        news_coro = asyncio.gather(
            *news_tasks,
            return_exceptions=True,
        )
        price_coro = asyncio.gather(
            *(provider.fetch_incremental() for provider in self.price_providers),
            return_exceptions=True,
        )

        # Await both together to maintain full concurrency
        news_results, price_results = await asyncio.gather(news_coro, price_coro)

        # Process news results - zip keeps provider and result matched
        for provider, result in zip(self.news_providers, news_results, strict=True):
            provider_name = getattr(provider, "source_name", provider.__class__.__name__)
            if isinstance(result, Exception):
                logger.debug(f"{provider_name} news fetch failed: {result}")
                errors.append(f"{provider_name}: {str(result)}")
            else:
                entries = cast(list[NewsEntry], result)
                if provider in self._finnhub_macro_providers:
                    macro_news.extend(entries)
                else:
                    company_news.extend(entries)

        # Process price results - keep providers separate
        for provider, result in zip(self.price_providers, price_results, strict=True):
            provider_name = getattr(provider, "source_name", provider.__class__.__name__)
            if isinstance(result, Exception):
                logger.debug(f"{provider_name} price fetch failed: {result}")
                errors.append(f"{provider_name}: {str(result)}")
            else:
                # Convert list to dict keyed by symbol
                prices = cast(list[PriceData], result)
                prices_by_provider[provider] = {p.symbol: p for p in prices}

        return DataBatch(
            company_news=company_news,
            macro_news=macro_news,
            prices=prices_by_provider,
            errors=errors,
        )

    async def _process_prices(
        self, prices_by_provider: dict[PriceDataSource, dict[str, PriceData]]
    ) -> int:
        """
        Deduplicate and store price data from multiple providers.

        Compares prices by symbol across providers. If prices differ by >= $0.01,
        logs an error. Always stores the primary provider's price (first in order).

        Args:
            prices_by_provider: Dict mapping provider name to symbol-keyed prices

        Returns:
            Number of prices stored
        """
        if not prices_by_provider:
            return 0

        # Primary provider = first in configured order
        provider_order = list(self.price_providers)
        primary_provider = provider_order[0]
        primary_provider_name = getattr(
            primary_provider, "source_name", primary_provider.__class__.__name__
        )

        # Get primary provider's prices (or empty dict if failed)
        primary_prices = prices_by_provider.get(primary_provider, {})

        # Collect all unique symbols across all providers
        all_symbols = set()
        for provider_prices in prices_by_provider.values():
            all_symbols.update(provider_prices.keys())

        # Compare and store
        deduplicated_prices = []
        for symbol in all_symbols:
            # Get primary provider's price
            primary_price_data = primary_prices.get(symbol)
            if primary_price_data is None:
                logger.warning(f"{primary_provider_name} missing price for {symbol}")
                continue

            # Always store primary provider's price
            deduplicated_prices.append(primary_price_data)

            # Skip comparison if only one provider configured
            if len(provider_order) == 1:
                continue

            for provider in provider_order[1:]:
                provider_prices = prices_by_provider.get(provider)
                provider_name = getattr(provider, "source_name", provider.__class__.__name__)
                if provider_prices is None:
                    continue

                other_price_data = provider_prices.get(symbol)
                if other_price_data is None:
                    logger.warning(f"{provider_name} missing price for {symbol}")
                    continue

                # Check for mismatch
                diff = abs(primary_price_data.price - other_price_data.price)
                if diff >= Decimal("0.01"):
                    logger.error(
                        f"Price mismatch for {symbol}: "
                        f"{primary_provider_name}=${primary_price_data.price} vs "
                        f"{provider_name}=${other_price_data.price} (diff=${diff})"
                    )

        await asyncio.to_thread(
            store_price_data,
            self.db_path,
            deduplicated_prices,
        )

        logger.info(f"Stored {len(deduplicated_prices)} price updates")
        return len(deduplicated_prices)

    def _log_urgent_items(self, urgent_items: list[NewsEntry]) -> None:
        """Summarize urgency detection results with bounded detail."""
        if not urgent_items:
            logger.debug("No urgent news items detected")
            return
        logger.warning(f"Found {len(urgent_items)} URGENT news items requiring attention")
        for item in urgent_items[:10]:
            logger.warning(f"URGENT [{item.symbol}]: {item.headline} - {item.url}")
        if len(urgent_items) > 10:
            logger.warning(f"... {len(urgent_items) - 10} more")

    async def _process_news(
        self, company_news: list[NewsEntry], macro_news: list[NewsEntry]
    ) -> int:
        """Store news, classify company news, detect urgency, and update watermarks."""
        all_news = company_news + macro_news

        # Store all news items
        await asyncio.to_thread(
            store_news_items,
            self.db_path,
            all_news,
        )

        # Detect urgent items from all news
        if all_news:
            try:
                self._log_urgent_items(detect_urgency(all_news))
            except (LLMError, ValueError, TypeError, RuntimeError) as exc:
                logger.exception(f"Urgency detection failed: {exc}")

        # Update watermark with latest timestamp from all news
        if all_news:
            max_time = max(n.published for n in all_news)
            await asyncio.to_thread(
                set_last_news_time,
                self.db_path,
                max_time,
            )

            # Persist minId watermark for macro news providers
            for provider in self._finnhub_macro_providers:
                if provider.last_fetched_max_id:
                    await asyncio.to_thread(
                        set_last_macro_min_id, self.db_path, provider.last_fetched_max_id
                    )
                    logger.info(
                        f"Updated macro news minId watermark to {provider.last_fetched_max_id}"
                    )

            logger.info(
                f"Stored {len(all_news)} news items "
                f"({len(company_news)} company, {len(macro_news)} macro), "
                f"watermark updated to {max_time.isoformat()}"
            )
        else:
            logger.info("No news items to process")

        return len(all_news)

    async def poll_once(self) -> PollStats:
        """
        Execute one polling cycle.

        Returns:
            PollStats with news count, prices count, and errors list
        """
        stats: PollStats = {"news": 0, "prices": 0, "errors": []}

        try:
            # Read watermarks for incremental fetching
            last_news_time, last_macro_min_id = await self._read_watermarks()

            if last_news_time:
                logger.info(f"Fetching news since {last_news_time.isoformat()}")
            else:
                logger.info("No watermark found, fetching all available news")

            if last_macro_min_id:
                logger.info(f"Fetching macro news with minId={last_macro_min_id}")

            # Fetch all data concurrently
            data = await self._fetch_all_data(last_news_time, last_macro_min_id)

            # Extract data from dict
            company_news = data["company_news"]
            macro_news = data["macro_news"]
            stats["errors"].extend(data["errors"])

            if company_news or macro_news:
                stats["news"] = await self._process_news(company_news, macro_news)
            else:
                logger.info("No new news items found")

            # Process prices
            prices_by_provider = data["prices"]

            if prices_by_provider:
                stats["prices"] = await self._process_prices(prices_by_provider)
            else:
                logger.info("No price data fetched")

        except (
            TimeoutError,
            DataSourceError,
            RetryableError,
            ValueError,
            TypeError,
            RuntimeError,
            OSError,
        ) as exc:
            logger.exception(f"Poll cycle failed with error: {exc}")
            stats["errors"].append(f"Cycle error: {exc}")

        return stats

    async def run(self) -> None:
        """
        Run continuous polling loop.

        Polls at specified interval until stop() is called.
        """

        self._stop_event.clear()
        self.running = True
        logger.info(f"Starting data poller with {self.poll_interval}s interval")

        # Run first poll immediately
        cycle_count = 0

        while self.running:  # pragma: no cover - run() sets running True before loop
            cycle_count += 1
            logger.info(f"Starting poll cycle #{cycle_count}")
            start_time = asyncio.get_running_loop().time()

            # Execute one poll cycle
            stats = await self.poll_once()

            # Log results
            if stats["errors"]:
                logger.warning(
                    f"Cycle #{cycle_count} completed with errors: "
                    f"{stats['news']} news, {stats['prices']} prices, "
                    f"Errors: {stats['errors']}"
                )
            else:
                logger.info(
                    f"Cycle #{cycle_count} completed successfully: "
                    f"{stats['news']} news, {stats['prices']} prices"
                )

            # Calculate sleep time to maintain consistent interval
            elapsed = asyncio.get_running_loop().time() - start_time
            sleep_time = max(0, self.poll_interval - elapsed)

            if self.running and sleep_time > 0:
                logger.info(f"Next poll in {sleep_time:.1f} seconds...")
                try:
                    # Wait for either the timeout or stop event
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_time)
                    # If we get here, stop was requested
                    logger.info("Stop event received during wait")
                    break
                except TimeoutError:
                    logger.debug("Poll wait timeout; continuing to next cycle")
                    continue
                except asyncio.CancelledError:
                    logger.info("Wait cancelled, exiting...")
                    break

    def stop(self) -> None:
        """Request graceful shutdown of the polling loop."""
        logger.info("Stopping poller...")
        self.running = False
        self._stop_event.set()
