"""Data poller for continuous market data collection.

Notes:
    Orchestrates fetching from configured providers at regular intervals,
    storing results in SQLite, managing watermarks for incremental fetching,
    and deduplicating prices from multiple providers.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any, TypedDict, cast

from analysis.news_importance import label_importance
from analysis.urgency_detector import detect_news_urgency, detect_social_urgency
from data import NewsDataSource, PriceDataSource, SocialDataSource
from data.models import NewsEntry, PriceData, SocialDiscussion
from data.storage import store_news_items, store_price_data, store_social_discussions
from llm.base import LLMError
from workflows.watermarks import CursorPlan, WatermarkEngine, is_macro_stream

logger = logging.getLogger(__name__)


class DataBatch(TypedDict):
    """Data fetched from all providers in one cycle."""

    company_news: list[NewsEntry]
    macro_news: list[NewsEntry]
    social_discussions: list[SocialDiscussion]
    prices: dict[PriceDataSource, dict[str, PriceData]]  # {provider: {symbol: PriceData}}
    news_by_provider: dict[NewsDataSource, list[NewsEntry]]
    social_by_provider: dict[SocialDataSource, list[SocialDiscussion]]
    errors: list[str]


class PollStats(TypedDict):
    """Statistics from one polling cycle."""

    news: int
    social: int
    prices: int
    errors: list[str]


class DataPoller:
    """Poll configured providers for news and price data at regular intervals.

    Notes:
        Handles watermark-based incremental fetching, partial failures, price
        deduplication across providers, and graceful shutdown.
    """

    def __init__(
        self,
        db_path: str,
        news_providers: list[NewsDataSource],
        social_providers: list[SocialDataSource],
        price_providers: list[PriceDataSource],
        poll_interval: int,
    ) -> None:
        """Initialize the data poller."""
        self.db_path = db_path
        self.news_providers = news_providers
        self.social_providers = social_providers
        self.price_providers = price_providers
        self.poll_interval = poll_interval
        self.running = False
        self._stop_event = asyncio.Event()
        self.watermarks = WatermarkEngine(db_path)

    @staticmethod
    def _plan_kwargs(plan: CursorPlan) -> dict[str, Any]:
        """Build keyword args for provider.fetch_incremental based on available cursors."""
        kwargs: dict[str, Any] = {}
        if plan.since is not None:
            kwargs["since"] = plan.since
        if plan.min_id is not None:
            kwargs["min_id"] = plan.min_id
        if plan.symbol_since_map is not None:
            kwargs["symbol_since_map"] = plan.symbol_since_map
        return kwargs

    async def _fetch_all_data(self) -> DataBatch:
        """Fetch data from all providers concurrently.

        Notes:
            Returns a ``DataBatch`` with company_news, macro_news, social_discussions,
            prices, and errors.
        """
        # Separate results by provider type
        company_news: list[NewsEntry] = []
        macro_news: list[NewsEntry] = []
        social_discussions: list[SocialDiscussion] = []
        prices_by_provider: dict[PriceDataSource, dict[str, PriceData]] = {}
        errors = []

        # Start news, social, and price fetches concurrently (don't await yet)
        news_tasks = []
        for provider in self.news_providers:
            plan = self.watermarks.build_plan(provider)
            news_tasks.append(provider.fetch_incremental(**self._plan_kwargs(plan)))

        social_tasks = []
        for provider in self.social_providers:
            plan = self.watermarks.build_plan(provider)
            social_tasks.append(provider.fetch_incremental(**self._plan_kwargs(plan)))

        news_coro = asyncio.gather(
            *news_tasks,
            return_exceptions=True,
        )
        price_coro = asyncio.gather(
            *(provider.fetch_incremental() for provider in self.price_providers),
            return_exceptions=True,
        )
        social_coro = asyncio.gather(
            *social_tasks,
            return_exceptions=True,
        )

        # Await both together to maintain full concurrency
        news_results, price_results, social_results = await asyncio.gather(
            news_coro, price_coro, social_coro
        )

        news_by_provider: dict[NewsDataSource, list[NewsEntry]] = {}
        social_by_provider: dict[SocialDataSource, list[SocialDiscussion]] = {}

        # Process news results - zip keeps provider and result matched
        for provider, result in zip(self.news_providers, news_results, strict=True):
            provider_name = getattr(provider, "source_name", provider.__class__.__name__)
            if isinstance(result, Exception):
                logger.debug("%s news fetch failed: %s", provider_name, result)
                errors.append(f"{provider_name}: {str(result)}")
                continue

            entries = cast(list[NewsEntry], result)
            news_by_provider[provider] = entries
            if is_macro_stream(provider):
                macro_news.extend(entries)
            else:
                company_news.extend(entries)

        # Process social results
        for provider, result in zip(self.social_providers, social_results, strict=True):
            provider_name = getattr(provider, "source_name", provider.__class__.__name__)
            if isinstance(result, Exception):
                logger.debug("%s social fetch failed: %s", provider_name, result)
                errors.append(f"{provider_name}: {str(result)}")
                continue

            items = cast(list[SocialDiscussion], result)
            social_by_provider[provider] = items
            social_discussions.extend(items)

        # Process price results - keep providers separate
        for provider, result in zip(self.price_providers, price_results, strict=True):
            provider_name = getattr(provider, "source_name", provider.__class__.__name__)
            if isinstance(result, Exception):
                logger.debug("%s price fetch failed: %s", provider_name, result)
                errors.append(f"{provider_name}: {str(result)}")
            else:
                # Convert list to dict keyed by symbol
                prices = cast(list[PriceData], result)
                prices_by_provider[provider] = {p.symbol: p for p in prices}

        return DataBatch(
            company_news=company_news,
            macro_news=macro_news,
            social_discussions=social_discussions,
            prices=prices_by_provider,
            news_by_provider=news_by_provider,
            social_by_provider=social_by_provider,
            errors=errors,
        )

    async def _process_prices(
        self, prices_by_provider: dict[PriceDataSource, dict[str, PriceData]]
    ) -> int:
        """Store only primary-provider prices; log mismatches >= $0.01.

        Notes:
            Uses the first configured price provider as the primary source.
            For each symbol, stores only the primary provider's price.

            If other providers disagree with the primary by at least ``$0.01``,
            logs an error. If the primary provider has no price for a symbol,
            that symbol is skipped (intentional).
        """
        if not prices_by_provider:
            logger.info("No price data fetched")
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
                logger.warning("%s missing price for %s", primary_provider_name, symbol)
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
                    logger.warning("%s missing price for %s", provider_name, symbol)
                    continue

                # Check for mismatch
                diff = abs(primary_price_data.price - other_price_data.price)
                if diff >= Decimal("0.01"):
                    logger.error(
                        "Price mismatch for %s: %s=$%s vs %s=$%s (diff=$%s)",
                        symbol,
                        primary_provider_name,
                        primary_price_data.price,
                        provider_name,
                        other_price_data.price,
                        diff,
                    )

        await asyncio.to_thread(
            store_price_data,
            self.db_path,
            deduplicated_prices,
        )

        logger.info("Stored %s price updates", len(deduplicated_prices))
        return len(deduplicated_prices)

    def _log_urgent_items(self, urgent_items: list[NewsEntry]) -> None:
        """Log up to 10 urgent news items (then a remainder count).

        Notes:
            Logs up to 10 urgent items (then a single "... N more" line).
        """
        if not urgent_items:
            logger.debug("No urgent news items detected")
            return
        logger.warning("Found %s URGENT news items requiring attention", len(urgent_items))
        for item in urgent_items[:10]:
            logger.warning("URGENT [%s]: %s - %s", item.symbol, item.headline, item.url)
        if len(urgent_items) > 10:
            logger.warning("... %s more", len(urgent_items) - 10)

    def _log_urgent_social(self, urgent_items: list[SocialDiscussion]) -> None:
        """Log up to 10 urgent social items (then a remainder count).

        Notes:
            Logs up to 10 urgent items (then a single "... N more" line).
        """
        if not urgent_items:
            logger.debug("No urgent social items detected")
            return
        logger.warning("Found %s URGENT social threads requiring attention", len(urgent_items))
        for item in urgent_items[:10]:
            logger.warning(
                "URGENT [%s] %s: %s - %s",
                item.symbol,
                item.community,
                item.title,
                item.url,
            )
        if len(urgent_items) > 10:
            logger.warning("... %s more", len(urgent_items) - 10)

    async def _process_news(
        self,
        news_by_provider: dict[NewsDataSource, list[NewsEntry]],
        company_news: list[NewsEntry],
        macro_news: list[NewsEntry],
    ) -> int:
        """Store news, detect urgency, and update per-provider watermarks."""
        all_news = company_news + macro_news
        if not all_news:
            logger.info("No news items to process")
        else:
            labeled_news = label_importance(all_news)
            await asyncio.to_thread(store_news_items, self.db_path, labeled_news)

            try:
                self._log_urgent_items(detect_news_urgency(all_news))
            except (LLMError, ValueError, TypeError, RuntimeError) as exc:
                logger.exception("Urgency detection failed: %s", exc)

        commit_tasks = [
            asyncio.to_thread(self.watermarks.commit_updates, provider, entries)
            for provider, entries in news_by_provider.items()
        ]
        if commit_tasks:
            await asyncio.gather(*commit_tasks)

        if all_news:
            logger.info(
                "Stored %s news items (%s company, %s macro)",
                len(all_news),
                len(company_news),
                len(macro_news),
            )
        return len(all_news)

    async def _process_social(
        self,
        social_by_provider: dict[SocialDataSource, list[SocialDiscussion]],
        social_discussions: list[SocialDiscussion],
    ) -> int:
        """Store social discussions and update watermarks."""
        if not social_discussions:
            logger.info("No social discussions to process")
        else:
            await asyncio.to_thread(store_social_discussions, self.db_path, social_discussions)

            try:
                self._log_urgent_social(detect_social_urgency(social_discussions))
            except (LLMError, ValueError, TypeError, RuntimeError) as exc:
                logger.exception("Social urgency detection failed: %s", exc)

        commit_tasks = [
            asyncio.to_thread(self.watermarks.commit_updates, provider, items)
            for provider, items in social_by_provider.items()
        ]
        if commit_tasks:
            await asyncio.gather(*commit_tasks)

        if social_discussions:
            logger.info("Stored %s social discussions", len(social_discussions))

        return len(social_discussions)

    async def poll_once(self) -> PollStats:
        """Execute one polling cycle.

        Notes:
            Returns a ``PollStats`` dict with news count, social count, prices count, and
            errors list.
        """
        stats: PollStats = {"news": 0, "social": 0, "prices": 0, "errors": []}

        try:
            # Fetch all data concurrently
            data = await self._fetch_all_data()

            # Extract data from dict
            company_news = data["company_news"]
            macro_news = data["macro_news"]
            social_discussions = data["social_discussions"]
            stats["errors"].extend(data["errors"])

            stats["news"] = await self._process_news(
                data["news_by_provider"], company_news, macro_news
            )

            stats["social"] = await self._process_social(
                data["social_by_provider"], social_discussions
            )

            # Process prices
            stats["prices"] = await self._process_prices(data["prices"])

        except (
            TimeoutError,
            ValueError,
            TypeError,
            RuntimeError,
            OSError,
        ) as exc:
            logger.exception("Poll cycle failed with error: %s", exc)
            stats["errors"].append(f"Cycle error: {exc}")

        return stats

    async def run(self) -> None:
        """Run the continuous polling loop.

        Notes:
            Polls at the configured interval until ``stop()`` is called.
        """

        self._stop_event.clear()
        self.running = True
        logger.info("Starting data poller with %ss interval", self.poll_interval)

        # Run first poll immediately
        cycle_count = 0

        while self.running:  # pragma: no cover - run() sets running True before loop
            cycle_count += 1
            logger.info("Starting poll cycle #%s", cycle_count)
            start_time = asyncio.get_running_loop().time()

            # Execute one poll cycle
            stats = await self.poll_once()

            # Log results
            if stats["errors"]:
                logger.warning(
                    "Cycle #%s completed with errors: %s news, %s social, %s prices, Errors: %s",
                    cycle_count,
                    stats["news"],
                    stats["social"],
                    stats["prices"],
                    stats["errors"],
                )
            else:
                logger.info(
                    "Cycle #%s completed successfully: %s news, %s social, %s prices",
                    cycle_count,
                    stats["news"],
                    stats["social"],
                    stats["prices"],
                )

            # Calculate sleep time to maintain consistent interval
            elapsed = asyncio.get_running_loop().time() - start_time
            sleep_time = max(0, self.poll_interval - elapsed)

            if self.running and sleep_time > 0:
                logger.info("Next poll in %.1f seconds...", sleep_time)
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
