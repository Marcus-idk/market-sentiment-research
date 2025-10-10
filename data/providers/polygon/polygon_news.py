"""Polygon.io company news provider implementation."""

import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any

from config.providers.polygon import PolygonSettings
from data import NewsDataSource, DataSourceError
from data.models import NewsItem
from data.providers.polygon.polygon_client import PolygonClient, _NEWS_LIMIT, _NEWS_ORDER
from data.storage.storage_utils import _datetime_to_iso, _parse_rfc3339
from utils.retry import RetryableError


logger = logging.getLogger(__name__)


class PolygonNewsProvider(NewsDataSource):
    """Fetches company-specific news from Polygon.io's /v2/reference/news endpoint.

    Rate Limits:
        Free tier: ~5 calls/min (shared with price provider).
        Each poll cycle makes one call per symbol, plus pagination if needed.
    """

    def __init__(
        self, settings: PolygonSettings, symbols: list[str], source_name: str = "Polygon"
    ) -> None:
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = PolygonClient(settings)

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        min_id: int | None = None,
    ) -> list[NewsItem]:
        if not self.symbols:
            return []

        now_utc = datetime.now(timezone.utc)

        if since is not None:
            buffer_time = since - timedelta(minutes=2)
        else:
            buffer_time = now_utc - timedelta(days=2)

        published_gt = _datetime_to_iso(buffer_time)

        news_items: list[NewsItem] = []

        for symbol in self.symbols:
            try:
                symbol_news = await self._fetch_symbol_news(
                    symbol, published_gt, buffer_time
                )
                news_items.extend(symbol_news)
            except DataSourceError:
                raise
            except (RetryableError, ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.warning(
                    f"Company news fetch failed for {symbol}: {exc}"
                )
                continue
            except Exception as exc:  # pragma: no cover - unexpected
                logger.exception(
                    f"Unexpected error fetching company news for {symbol}: {exc}"
                )
                continue

        return news_items

    async def _fetch_symbol_news(
        self,
        symbol: str,
        published_gt: str,
        buffer_time: datetime | None,
    ) -> list[NewsItem]:
        """Fetch all news for a symbol, following pagination until complete."""
        news_items: list[NewsItem] = []
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
                        f"Polygon company news expected dict response, got {type(response).__name__}"
                    )

                articles = response.get("results", [])
                if not isinstance(articles, list):
                    raise DataSourceError(
                        f"Polygon company news 'results' field is {type(articles).__name__}, expected list"
                    )
                if not articles:
                    break

                # Parse articles
                for article in articles:
                    try:
                        news_item = self._parse_article(article, symbol, buffer_time)
                        if news_item:
                            news_items.append(news_item)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        logger.debug(
                            f"Failed to parse company news article for {symbol}: {exc}"
                        )
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
                logger.warning(
                    f"Company news pagination failed for {symbol}: {exc}"
                )
                raise
            except Exception as exc:  # pragma: no cover - unexpected
                logger.exception(
                    f"Unexpected error during company news pagination for {symbol}: {exc}"
                )
                raise

        return news_items

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
    ) -> NewsItem | None:
        """Parse Polygon news article into NewsItem."""
        title = article.get("title", "").strip()
        article_url = article.get("article_url", "").strip()
        published_utc = article.get("published_utc", "").strip()

        if not title or not article_url or not published_utc:
            return None

        # Parse RFC3339 timestamp
        try:
            published = _parse_rfc3339(published_utc)
        except (ValueError, TypeError) as exc:  # pragma: no cover
            logger.debug(
                f"Skipping company news article for {symbol} due to invalid timestamp {published_utc}: {exc}"
            )
            return None

        # Apply buffer filter (defensive check - API should already filter via published_utc.gt)
        if buffer_time and published <= buffer_time:
            logger.warning(
                f"Polygon API returned article with published={published.isoformat()} "
                f"despite published_utc.gt={_datetime_to_iso(buffer_time)} filter - possible API contract violation"
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
            return NewsItem(
                symbol=symbol,
                url=article_url,
                headline=title,
                published=published,
                source=source,
                content=content,
            )
        except ValueError as exc:
            logger.debug(
                f"NewsItem validation failed for {symbol} (url={article_url}): {exc}"
            )
            return None
