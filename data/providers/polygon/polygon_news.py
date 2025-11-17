"""Polygon.io company news provider implementation."""

import logging
import urllib.parse
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
from data.providers.polygon.polygon_client import _NEWS_LIMIT, _NEWS_ORDER, PolygonClient
from data.storage.storage_utils import _datetime_to_iso, _parse_rfc3339
from utils.retry import RetryableError

logger = logging.getLogger(__name__)


class PolygonNewsProvider(NewsDataSource):
    """Fetches company-specific news from Polygon.io's /v2/reference/news endpoint.

    Rate Limits:
        Free tier: ~5 calls/min (shared across all Polygon endpoints).
        Each poll cycle makes one call per symbol, plus pagination if needed.
    """

    def __init__(
        self, settings: PolygonSettings, symbols: list[str], source_name: str = "Polygon"
    ) -> None:
        super().__init__(source_name)
        self.settings = settings
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = PolygonClient(settings)

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        symbol_since_map: dict[str, datetime | None] | None = None,
    ) -> list[NewsEntry]:
        if not self.symbols:
            return []

        now_utc = datetime.now(UTC)
        overlap_delta = timedelta(minutes=self.settings.company_news_overlap_minutes)
        bootstrap_delta = timedelta(days=self.settings.company_news_first_run_days)

        news_entries: list[NewsEntry] = []

        for symbol in self.symbols:
            try:
                symbol_cursor = self._resolve_symbol_cursor(symbol, symbol_since_map, since)
                if symbol_cursor is not None:
                    start_time = symbol_cursor - overlap_delta
                else:
                    start_time = now_utc - bootstrap_delta

                if start_time > now_utc:
                    start_time = now_utc

                # Buffer matches start_time to keep all articles in the overlap window.
                # This allows us to catch delayed articles (published before cursor but
                # not yet visible in the API). The database handles deduplication by URL.
                # Downstream systems (Poller, urgency) will see overlap articles again,
                # but this is intentional to ensure we never miss late-arriving news.
                buffer_time = start_time

                published_gt = _datetime_to_iso(start_time)
                symbol_news = await self._fetch_symbol_news(symbol, published_gt, buffer_time)
                news_entries.extend(symbol_news)
            except (RetryableError, ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.warning(f"Company news fetch failed for {symbol}: {exc}")
                continue

        return news_entries

    def _resolve_symbol_cursor(
        self,
        symbol: str,
        symbol_since_map: dict[str, datetime | None] | None,
        global_since: datetime | None,
    ) -> datetime | None:
        if symbol_since_map is not None and symbol in symbol_since_map:
            return symbol_since_map[symbol]
        return global_since

    async def _fetch_symbol_news(
        self,
        symbol: str,
        published_gt: str,
        buffer_time: datetime | None,
    ) -> list[NewsEntry]:
        """Fetch all news for a symbol, following pagination until complete."""
        news_entries: list[NewsEntry] = []
        cursor: str | None = None

        while True:
            try:
                # Build request params
                params: dict[str, Any] = {
                    "ticker": symbol,
                    "published_utc.gt": published_gt,
                    "limit": _NEWS_LIMIT,
                    "order": _NEWS_ORDER,
                }

                if cursor:
                    params["cursor"] = cursor

                response = await self.client.get("/v2/reference/news", params)

                if not isinstance(response, dict):
                    raise DataSourceError(
                        "Polygon company news expected dict response, got "
                        f"{type(response).__name__}"
                    )

                articles = response.get("results", [])
                if not isinstance(articles, list):
                    raise DataSourceError(
                        "Polygon company news 'results' field is "
                        f"{type(articles).__name__}, expected list"
                    )
                if not articles:
                    break

                # Parse articles
                for article in articles:
                    try:
                        entry = self._parse_article(article, symbol, buffer_time)
                        if entry:
                            news_entries.append(entry)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        logger.debug(f"Failed to parse company news article for {symbol}: {exc}")
                        continue

                # Check for next page
                next_url = response.get("next_url")
                if not next_url:
                    break

                # Extract cursor from next_url
                cursor = self._extract_cursor(next_url)
                if not cursor:
                    break

            except (
                RetryableError,
                DataSourceError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                logger.warning(f"Company news pagination failed for {symbol}: {exc}")
                raise

        return news_entries

    def _extract_cursor(self, next_url: str) -> str | None:
        """Extract cursor parameter from Polygon next_url."""
        try:
            parsed = urllib.parse.urlparse(next_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            cursor = query_params.get("cursor", [None])[0]
            return cursor
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.debug(f"Failed to extract cursor from next_url: {exc}")
            return None

    def _parse_article(
        self,
        article: dict[str, Any],
        symbol: str,
        buffer_time: datetime | None,
    ) -> NewsEntry | None:
        """Parse Polygon news article into a NewsEntry."""
        title = article.get("title", "").strip()
        article_url = article.get("article_url", "").strip()
        published_utc = article.get("published_utc", "").strip()

        if not title or not article_url or not published_utc:
            return None

        # Parse RFC3339 timestamp
        try:
            published = _parse_rfc3339(published_utc)
        except (ValueError, TypeError) as exc:
            logger.debug(
                f"Skipping company news article for {symbol} due to invalid timestamp "
                f"{published_utc}: {exc}"
            )
            return None

        # Apply buffer filter (defensive check - API should already filter via published_utc.gt)
        if buffer_time and published <= buffer_time:
            logger.warning(
                f"Polygon API returned article with published="
                f"{published.isoformat()} "
                f"despite published_utc.gt={_datetime_to_iso(buffer_time)} filter - "
                f"possible API contract violation"
            )
            return None

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
                news_type=NewsType.COMPANY_SPECIFIC,
                content=content,
            )
            return NewsEntry(article=article_model, symbol=symbol, is_important=True)
        except ValueError as exc:
            logger.debug(f"NewsItem validation failed for {symbol} (url={article_url}): {exc}")
            return None
