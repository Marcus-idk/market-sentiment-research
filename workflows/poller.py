"""
Data poller for continuous market data collection.

Orchestrates fetching from Finnhub providers every 5 minutes,
storing results in SQLite, and managing watermarks for incremental fetching.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, TypedDict

from data.models import NewsItem, PriceData
from data.storage import (
    get_last_news_time, set_last_news_time,
    get_last_macro_min_id, set_last_macro_min_id,
    store_news_items, store_price_data, store_news_labels
)
from data.base import NewsDataSource, PriceDataSource
from data.providers.finnhub import FinnhubMacroNewsProvider
from analysis.news_classifier import classify
from analysis.urgency_detector import detect_urgency

logger = logging.getLogger(__name__)


class DataBatch(TypedDict):
    """Data fetched from all providers in one cycle."""
    company_news: list[NewsItem]
    macro_news: list[NewsItem]
    prices: list[PriceData]
    errors: list[str]

class PollStats(TypedDict):
    """Statistics from one polling cycle."""
    news: int
    prices: int
    errors: list[str]


class DataPoller:
    """
    Polls Finnhub for news and price data at regular intervals.

    Handles watermark-based incremental fetching, partial failures,
    and graceful shutdown.
    """

    def __init__(
        self,
        db_path: str,
        news_providers: list[NewsDataSource],
        price_providers: list[PriceDataSource],
        poll_interval: int
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

        # Identify macro providers once at init (avoid isinstance in hot path)
        self._macro_providers = {
            provider for provider in news_providers
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
        company_news = []
        macro_news = []
        prices = []
        errors = []

        # Start both news and price fetches concurrently (don't await yet)
        news_coro = asyncio.gather(
            *(provider.fetch_incremental(since=last_news_time, min_id=last_macro_min_id)
              for provider in self.news_providers),
            return_exceptions=True
        )
        price_coro = asyncio.gather(
            *(provider.fetch_incremental() for provider in self.price_providers),
            return_exceptions=True
        )

        # Await both together to maintain full concurrency
        news_results, price_results = await asyncio.gather(news_coro, price_coro)

        # Process news results - zip keeps provider and result matched
        for provider, result in zip(self.news_providers, news_results):
            if isinstance(result, Exception):
                provider_name = provider.__class__.__name__
                logger.error(f"{provider_name} news fetch failed: {result}")
                errors.append(f"{provider_name}: {str(result)}")
            else:
                if provider in self._macro_providers:
                    macro_news.extend(result)
                else:
                    company_news.extend(result)

        # Process price results - zip keeps provider and result matched
        for provider, result in zip(self.price_providers, price_results):
            if isinstance(result, Exception):
                provider_name = provider.__class__.__name__
                logger.error(f"{provider_name} price fetch failed: {result}")
                errors.append(f"{provider_name}: {str(result)}")
            else:
                prices.extend(result)

        return DataBatch(
            company_news=company_news,
            macro_news=macro_news,
            prices=prices,
            errors=errors,
        )

    async def _process_prices(self, price_items: list[PriceData]) -> int:
        """Store price data."""

        await asyncio.to_thread(
            store_price_data,
            self.db_path,
            price_items,
        )

        logger.info(f"Stored {len(price_items)} price updates")
        return len(price_items)

    def _log_urgent_items(self, urgent_items: list[NewsItem]) -> None:
        """Summarize urgency detection results with bounded detail."""
        if not urgent_items:
            logger.debug("No urgent news items detected")
            return
        logger.warning(
            f"Found {len(urgent_items)} URGENT news items requiring attention"
        )
        for item in urgent_items[:10]:
            logger.warning(f"URGENT [{item.symbol}]: {item.headline} - {item.url}")
        if len(urgent_items) > 10:
            logger.warning(f"... {len(urgent_items) - 10} more")

    async def _process_news(self, company_news: list[NewsItem], macro_news: list[NewsItem]) -> int:
        """Store news, classify company news, detect urgency, and update watermarks."""
        all_news = company_news + macro_news

        # Store all news items
        await asyncio.to_thread(
            store_news_items,
            self.db_path,
            all_news,
        )

        # Classify ONLY company news (skip macro news)
        if company_news:
            try:
                labels = classify(company_news)
                if labels:
                    await asyncio.to_thread(
                        store_news_labels,
                        self.db_path,
                        labels
                    )
                    logger.info(f"Classified {len(labels)} company news items")
            except Exception:
                logger.exception("News classification failed")

        # Detect urgent items from all news
        if all_news:
            try:
                self._log_urgent_items(detect_urgency(all_news))
            except Exception:
                logger.exception("Urgency detection failed")

        # Update watermark with latest timestamp from all news
        max_time = max(n.published for n in all_news)
        await asyncio.to_thread(
            set_last_news_time,
            self.db_path,
            max_time,
        )

        # Persist minId watermark for macro news providers
        for provider in self._macro_providers:
            if provider.last_fetched_max_id:
                await asyncio.to_thread(
                    set_last_macro_min_id,
                    self.db_path,
                    provider.last_fetched_max_id
                )
                logger.info(f"Updated macro news minId watermark to {provider.last_fetched_max_id}")

        logger.info(
            f"Stored {len(all_news)} news items "
            f"({len(company_news)} company, {len(macro_news)} macro), "
            f"watermark updated to {max_time.isoformat()}"
        )

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
            prices = data["prices"]

            if prices:
                stats["prices"] = await self._process_prices(prices)
            else:
                logger.info("No price data fetched")

        except Exception as e:
            logger.exception(f"Poll cycle failed with unexpected error: {e}")
            stats["errors"].append(f"Cycle error: {str(e)}")

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

        while self.running:
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
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=sleep_time
                    )
                    # If we get here, stop was requested
                    logger.info("Stop event received during wait")
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue to next cycle
                    pass
                except asyncio.CancelledError:
                    logger.info("Wait cancelled, exiting...")
                    break

    def stop(self) -> None:
        """Request graceful shutdown of the polling loop."""
        logger.info("Stopping poller...")
        self.running = False
        self._stop_event.set()
