"""Polygon.io macro news provider implementation."""

import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any

from config.providers.polygon import PolygonSettings
from data import NewsDataSource, DataSourceError
from data.models import NewsItem
from utils.symbols import parse_symbols
from data.providers.polygon.polygon_client import PolygonClient, _NEWS_LIMIT, _NEWS_ORDER
from data.storage.storage_utils import _datetime_to_iso, _parse_rfc3339
from utils.retry import RetryableError


logger = logging.getLogger(__name__)


class PolygonMacroNewsProvider(NewsDataSource):
    """Fetches market-wide macro news from Polygon.io's /v2/reference/news endpoint.

    Fetches general market news (no ticker filter) and maps articles to watchlist
    symbols based on the tickers array in each article. Falls back to 'ALL' for
    articles that don't match any watchlist symbols.

    Rate Limits:
        Free tier: ~5 calls/min (shared with other Polygon providers).
        Each poll cycle makes pagination requests until complete.
    """

    def __init__(
        self, settings: PolygonSettings, symbols: list[str], source_name: str = "Polygon Macro"
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
        now_utc = datetime.now(timezone.utc)

        # Calculate time filter
        if since is not None:
            buffer_time = since - timedelta(minutes=2)
        else:
            buffer_time = now_utc - timedelta(days=2)

        published_gt = _datetime_to_iso(buffer_time)

        news_items: list[NewsItem] = []
        cursor: str | None = None

        while True:
            try:
                # Build request params (no ticker filter = general market news)
                params: dict[str, Any] = {
                    "published_utc.gt": published_gt,
                    "limit": _NEWS_LIMIT,
                    "order": _NEWS_ORDER,
                }

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

                # Parse articles
                for article in articles:
                    try:
                        items = self._parse_article(article, buffer_time)
                        news_items.extend(items)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        logger.debug(
                            f"Failed to parse macro news article {article.get('id', 'unknown')}: {exc}"
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
                    f"Macro news pagination failed: {exc}"
                )
                raise
            except Exception as exc:  # pragma: no cover - unexpected
                logger.exception(
                    f"Unexpected error during macro news pagination: {exc}"
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
        buffer_time: datetime | None,
    ) -> list[NewsItem]:
        """Parse Polygon news article into multiple NewsItems (one per matching symbol)."""
        title = article.get("title", "").strip()
        article_url = article.get("article_url", "").strip()
        published_utc = article.get("published_utc", "").strip()

        if not title or not article_url or not published_utc:
            return []

        # Parse RFC3339 timestamp
        try:
            published = _parse_rfc3339(published_utc)
        except (ValueError, TypeError) as exc:  # pragma: no cover
            logger.debug(
                f"Skipping macro news article due to invalid timestamp {published_utc}: {exc}"
            )
            return []

        # Apply buffer filter (defensive check - API should already filter via published_utc.gt)
        if buffer_time and published <= buffer_time:
            logger.warning(
                f"Polygon API returned article with published={published.isoformat()} "
                f"despite published_utc.gt={_datetime_to_iso(buffer_time)} filter - possible API contract violation"
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

        # Create NewsItem for each symbol
        news_items: list[NewsItem] = []
        for symbol in symbols:
            try:
                news_item = NewsItem(
                    symbol=symbol,
                    url=article_url,
                    headline=title,
                    published=published,
                    source=source,
                    content=content,
                )
                news_items.append(news_item)
            except ValueError as exc:
                logger.debug(
                    f"NewsItem validation failed for {symbol} (url={article_url}): {exc}"
                )
                continue

        return news_items

    def _extract_symbols_from_tickers(self, tickers: list[str] | None) -> list[str]:
        """Extract symbols from tickers array, filtering to watchlist. Fall back to ['ALL']."""
        if not tickers or not isinstance(tickers, list):
            return ["ALL"]

        # Convert tickers list to comma-separated string for parse_symbols
        tickers_str = ",".join(str(t) for t in tickers if t)

        symbols = parse_symbols(
            tickers_str,
            filter_to=self.symbols,
            validate=True,
            log_label="TICKERS",
        )

        if not symbols:
            return ["ALL"]

        return symbols
