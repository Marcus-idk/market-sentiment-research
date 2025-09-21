"""
Data poller for continuous market data collection.

Orchestrates fetching from Finnhub providers every 5 minutes,
storing results in SQLite, and managing watermarks for incremental fetching.
"""

import asyncio
import logging
from typing import Any, Dict, List

from data.models import NewsItem, PriceData
from data.storage import (
    get_last_news_time, set_last_news_time,
    store_news_items, store_price_data, store_news_labels
)
from data.base import NewsDataSource, PriceDataSource
from analysis.news_classifier import classify

logger = logging.getLogger(__name__)


class DataPoller:
    """
    Polls Finnhub for news and price data at regular intervals.

    Handles watermark-based incremental fetching, partial failures,
    and graceful shutdown.
    """

    def __init__(
        self,
        db_path: str,
        news_providers: List[NewsDataSource],
        price_providers: List[PriceDataSource],
        poll_interval: int
    ):
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

    async def poll_once(self) -> Dict[str, Any]:
        """
        Execute one polling cycle.

        Returns:
            Dict with stats: {"news": count, "prices": count, "errors": list}
        """
        stats = {"news": 0, "prices": 0, "errors": []}

        try:
            # Read watermark for incremental news fetching (offload blocking I/O)
            last_news_time = await asyncio.to_thread(
                get_last_news_time,
                self.db_path,
            )
            if last_news_time:
                logger.info(f"Fetching news since {last_news_time.isoformat()}")
            else:
                logger.info("No watermark found, fetching all available news")

            # Create tasks for all providers
            news_tasks = [
                provider.fetch_incremental(last_news_time)
                for provider in self.news_providers
            ]
            price_tasks = [
                provider.fetch_incremental()
                for provider in self.price_providers
            ]

            # Fetch all data concurrently
            all_tasks = news_tasks + price_tasks
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # Split results back into news and prices
            news_results = results[:len(news_tasks)]
            price_results = results[len(news_tasks):]

            # Collect all successful news items
            all_news = []
            for i, news_result in enumerate(news_results):
                if isinstance(news_result, Exception):
                    provider_name = self.news_providers[i].__class__.__name__
                    logger.error(f"{provider_name} news fetch failed: {news_result}")
                    stats["errors"].append(f"{provider_name}: {str(news_result)}")
                else:
                    all_news.extend(news_result)

            # Store all news at once (dedup happens in storage)
            if all_news:
                await asyncio.to_thread(
                    store_news_items,
                    self.db_path,
                    all_news,
                )
                stats["news"] = len(all_news)

                # Classify the news items
                try:
                    labels = classify(all_news)
                    if labels:
                        await asyncio.to_thread(
                            store_news_labels,
                            self.db_path,
                            labels
                        )
                        logger.info(f"Classified {len(labels)} news items")
                except Exception as e:
                    logger.warning(f"News classification failed: {e}")

                # Update watermark with latest timestamp
                max_time = max(n.published for n in all_news)
                await asyncio.to_thread(
                    set_last_news_time,
                    self.db_path,
                    max_time,
                )
                logger.info(f"Stored {len(all_news)} news items, watermark updated to {max_time.isoformat()}")
            else:
                logger.info("No new news items found")

            # Collect all successful price data
            all_prices = []
            for i, price_result in enumerate(price_results):
                if isinstance(price_result, Exception):
                    provider_name = self.price_providers[i].__class__.__name__
                    logger.error(f"{provider_name} price fetch failed: {price_result}")
                    stats["errors"].append(f"{provider_name}: {str(price_result)}")
                else:
                    all_prices.extend(price_result)

            # Store all prices at once
            if all_prices:
                await asyncio.to_thread(
                    store_price_data,
                    self.db_path,
                    all_prices,
                )
                stats["prices"] = len(all_prices)
                logger.info(f"Stored {len(all_prices)} price updates")
            else:
                logger.info("No price data fetched")

        except Exception as e:
            logger.error(f"Poll cycle failed with unexpected error: {e}", exc_info=True)
            stats["errors"].append(f"Cycle error: {str(e)}")

        return stats

    async def run(self):
        """
        Run continuous polling loop.

        Polls at specified interval until stop() is called.
        """
        self.running = True
        logger.info(f"Starting data poller with {self.poll_interval}s interval")

        # Run first poll immediately
        cycle_count = 0

        while self.running:
            cycle_count += 1
            logger.info(f"Starting poll cycle #{cycle_count}")
            start_time = asyncio.get_event_loop().time()

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
            elapsed = asyncio.get_event_loop().time() - start_time
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

    def stop(self):
        logger.info("Stopping poller...")
        self.running = False
        self._stop_event.set()
