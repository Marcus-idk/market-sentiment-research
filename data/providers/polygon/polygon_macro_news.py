"""Polygon.io macro news provider implementation."""

import logging
from datetime import (
    UTC,
    datetime,
    timedelta,
    timezone,  # noqa: F401 - used by tests via monkeypatch
)
from typing import Any

from config.providers.polygon import PolygonSettings
from data import DataSourceError, NewsDataSource
from data.models import NewsEntry, NewsItem, NewsType
from data.providers.polygon.polygon_client import (
    NEWS_LIMIT,
    NEWS_ORDER,
    PolygonClient,
    _extract_cursor_from_next_url,
)
from data.storage.storage_utils import _datetime_to_iso
from utils.datetime_utils import parse_rfc3339
from utils.retry import RetryableError
from utils.symbols import parse_symbols

logger = logging.getLogger(__name__)


class PolygonMacroNewsProvider(NewsDataSource):
    """Fetches macro/market news from Polygon.io's /v2/reference/news endpoint."""

    def __init__(
        self, settings: PolygonSettings, symbols: list[str], source_name: str = "Polygon Macro"
    ) -> None:
        """Initialize the Polygon macro news provider."""
        super().__init__(source_name)
        self.settings = settings
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = PolygonClient(settings)

    async def validate_connection(self) -> bool:
        """Return True when the Polygon API is reachable."""
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
    ) -> list[NewsEntry]:
        """Fetch macro news stream incrementally with overlap handling."""
        now_utc = datetime.now(UTC)

        overlap_delta = timedelta(minutes=self.settings.macro_news_overlap_minutes)
        bootstrap_delta = timedelta(days=self.settings.macro_news_first_run_days)

        if since is not None:
            start_time = since - overlap_delta
        else:
            start_time = now_utc - bootstrap_delta

        if start_time > now_utc:
            start_time = now_utc

        published_gt = _datetime_to_iso(start_time)

        news_entries: list[NewsEntry] = []
        cursor: str | None = None

        while True:
            try:
                # Build request params (no ticker filter = general market news)
                params: dict[str, Any] = {
                    "published_utc.gt": published_gt,
                    "limit": NEWS_LIMIT,
                    "order": NEWS_ORDER,
                }

                # Add cursor for pagination (first loop None)
                if cursor:
                    params["cursor"] = cursor

                response = await self.client.get("/v2/reference/news", params)

                if not isinstance(response, dict):
                    raise DataSourceError(
                        f"Polygon API returned {type(response).__name__} instead of dict"
                    )

                articles = response.get("results", [])

                if not isinstance(articles, list):
                    raise DataSourceError(
                        f"Polygon API results field is {type(articles).__name__}, expected list"
                    )

                if not articles:
                    break

                for article in articles:
                    try:
                        items = self._parse_article(article, start_time)
                        news_entries.extend(items)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        logger.debug(
                            f"Failed to parse macro news article "
                            f"{article.get('id', 'unknown')}: {exc}"
                        )
                        continue

                # Check for next page
                next_url = response.get("next_url")
                if not next_url:
                    break

                # Extract cursor from next_url
                cursor = _extract_cursor_from_next_url(next_url)
                if not cursor:
                    break

            except (
                RetryableError,
                DataSourceError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                logger.warning(f"Macro news pagination failed: {exc}")
                raise

        return news_entries

    @staticmethod
    def _extract_cursor(next_url: str | None) -> str | None:
        """Extract cursor parameter from a Polygon next_url pagination link."""
        if next_url is None:
            return None
        return _extract_cursor_from_next_url(next_url)

    def _parse_article(
        self,
        article: dict[str, Any],
        buffer_time: datetime | None,
    ) -> list[NewsEntry]:
        """Parse Polygon news article into multiple NewsItems (one per matching symbol).

        Notes:
            Returns an empty list when required fields are missing/invalid or the article is
            at/before the buffer cutoff.
        """
        title = article.get("title", "").strip()
        article_url = article.get("article_url", "").strip()
        published_utc = article.get("published_utc", "").strip()

        if not title or not article_url or not published_utc:
            return []

        # Parse RFC3339 timestamp
        try:
            published = parse_rfc3339(published_utc)
        except (ValueError, TypeError) as exc:
            logger.debug(
                f"Skipping macro news article due to invalid timestamp {published_utc}: {exc}"
            )
            return []

        # Apply buffer filter (defensive check - API should already filter via published_utc.gt)
        if buffer_time and published <= buffer_time:
            cutoff_iso = _datetime_to_iso(buffer_time)
            published_iso = _datetime_to_iso(published)
            logger.warning(
                f"Polygon API returned article with published={published_iso} "
                f"despite published_utc.gt={cutoff_iso} filter - possible API contract violation"
            )
            return []

        # Extract symbols from tickers array
        tickers = article.get("tickers", [])
        symbols = self._extract_symbols_from_tickers(tickers)

        # Extract source from publisher
        publisher = article.get("publisher", {})
        if isinstance(publisher, dict):
            source = publisher.get("name", "").strip() or "Polygon"
        else:
            source = "Polygon"

        # Extract content from description
        description = article.get("description", "").strip()
        content = description if description else None

        try:
            article_model = NewsItem(
                url=article_url,
                headline=title,
                published=published,
                source=source,
                news_type=NewsType.MACRO,
                content=content,
            )
        except ValueError as exc:
            logger.debug(f"NewsItem validation failed (url={article_url}): {exc}")
            return []

        entries: list[NewsEntry] = []
        for symbol in symbols:
            try:
                entries.append(NewsEntry(article=article_model, symbol=symbol, is_important=None))
            except ValueError as exc:
                logger.debug(f"NewsEntry validation failed for {symbol} (url={article_url}): {exc}")
                continue

        return entries

    def _extract_symbols_from_tickers(self, tickers: list[str] | None) -> list[str]:
        """Extract symbols from tickers array, filtering to watchlist. Fall back to ['MARKET']."""
        if not tickers or not isinstance(tickers, list):
            return ["MARKET"]

        # Convert tickers list to comma-separated string for parse_symbols
        tickers_str = ",".join(str(t) for t in tickers if t)

        symbols = parse_symbols(
            tickers_str,
            filter_to=self.symbols,
            validate=True,
        )

        if not symbols:
            return ["MARKET"]

        return symbols
