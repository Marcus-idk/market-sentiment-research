"""Company news provider implementation."""

import logging
from collections.abc import Mapping
from datetime import (
    UTC,
    datetime,
    timedelta,
    timezone,  # noqa: F401 - used by tests via monkeypatch
)
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data import DataSourceError, NewsDataSource
from data.models import NewsEntry, NewsItem, NewsType
from data.providers.finnhub.finnhub_client import FinnhubClient
from utils.datetime_utils import epoch_seconds_to_utc_datetime
from utils.retry import RetryableError
from utils.symbols import normalize_symbol_list

logger = logging.getLogger(__name__)


class FinnhubNewsProvider(NewsDataSource):
    """Fetches company news from Finnhub's /company-news endpoint."""

    def __init__(
        self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub"
    ) -> None:
        """Initialize the Finnhub company news provider."""
        super().__init__(source_name)
        self.settings = settings
        self.symbols = normalize_symbol_list(symbols)
        self.client = FinnhubClient(settings)

    async def validate_connection(self) -> bool:
        """Return True when the Finnhub API is reachable."""
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        symbol_since_map: Mapping[str, datetime] | None = None,
    ) -> list[NewsEntry]:
        """Fetch company news for tracked symbols using overlap cursors."""
        if not self.symbols:
            return []

        now_utc = datetime.now(UTC)
        overlap_delta = timedelta(minutes=self.settings.company_news_overlap_minutes)
        bootstrap_delta = timedelta(days=self.settings.company_news_first_run_days)

        # Finnhub's /company-news endpoint requires from/to date parameters
        to_date = now_utc.date()
        news_entries: list[NewsEntry] = []

        for symbol in self.symbols:
            # Prefer per-symbol cursor; fall back to global since
            symbol_cursor = self._resolve_symbol_cursor(symbol, symbol_since_map, since)
            if symbol_cursor is not None:
                start_time = symbol_cursor - overlap_delta
            else:
                start_time = now_utc - bootstrap_delta

            # Make sure start_time is not in the future (API might return wrong)
            if start_time > now_utc:
                start_time = now_utc

            from_date = start_time.date()

            try:
                params = {
                    "symbol": symbol,
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                }

                articles = await self.client.get("/company-news", params)

                if not isinstance(articles, list):
                    raise DataSourceError(
                        f"Finnhub API returned {type(articles).__name__} instead of list"
                    )

                for article in articles:
                    try:
                        entry = self._parse_article(article, symbol, start_time)
                        if entry:
                            news_entries.append(entry)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        logger.debug(
                            "Failed to parse company news article for %s (url=%s): %s",
                            symbol,
                            article.get("url", "unknown"),
                            exc,
                        )
                        continue
            except (
                DataSourceError,
                RetryableError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
            ) as exc:
                logger.warning("Company news fetch failed for %s: %s", symbol, exc)
                continue

        return news_entries

    def _resolve_symbol_cursor(
        self,
        symbol: str,
        symbol_since_map: Mapping[str, datetime] | None,
        global_since: datetime | None,
    ) -> datetime | None:
        """Pick the most specific cursor for a symbol (per-symbol over global)."""
        # NOTE: Duplicated in other providers; consider extracting a shared helper
        # (e.g., in data/base.py).
        if symbol_since_map is not None and symbol in symbol_since_map:
            return symbol_since_map[symbol]
        return global_since

    def _parse_article(
        self,
        article: dict[str, Any],
        symbol: str,
        buffer_time: datetime | None,
    ) -> NewsEntry | None:
        """Parse Finnhub company news article into a NewsEntry.

        Notes:
            Returns None when required fields are missing/invalid or the article is at/before
            the buffer cutoff.
        """
        headline_value = article.get("headline")
        headline = headline_value.strip() if isinstance(headline_value, str) else ""
        url_value = article.get("url")
        url = url_value.strip() if isinstance(url_value, str) else ""
        datetime_epoch = article.get("datetime")

        if (
            not headline
            or not url
            or not isinstance(datetime_epoch, (int, float))
            or datetime_epoch <= 0
        ):
            logger.debug(
                "Skipping company news article for %s due to missing required fields "
                "(url=%s datetime=%r)",
                symbol,
                article.get("url", ""),
                article.get("datetime"),
            )
            return None

        try:
            published = epoch_seconds_to_utc_datetime(datetime_epoch)
        except (ValueError, OSError, OverflowError) as exc:
            logger.debug(
                "Skipping company news article for %s due to invalid epoch %s: %s",
                symbol,
                datetime_epoch,
                exc,
            )
            return None

        # Apply buffer filter (defensive check - API should already honor from/to dates)
        if buffer_time and published <= buffer_time:
            return None

        # Extract source and content
        source_value = article.get("source")
        source = source_value.strip() if isinstance(source_value, str) else ""
        source = source or "Finnhub"
        summary_value = article.get("summary")
        summary = summary_value.strip() if isinstance(summary_value, str) else ""
        content = summary if summary else None

        try:
            article_model = NewsItem(
                url=url,
                headline=headline,
                published=published,
                source=source,
                news_type=NewsType.COMPANY_SPECIFIC,
                content=content,
            )
            return NewsEntry(article=article_model, symbol=symbol, is_important=True)
        except ValueError as exc:
            logger.debug("NewsItem validation failed for %s (url=%s): %s", symbol, url, exc)
            return None
