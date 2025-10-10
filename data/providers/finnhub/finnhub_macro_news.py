"""Macro news provider implementation."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data import NewsDataSource, DataSourceError
from data.models import NewsItem
from utils.symbols import parse_symbols
from data.providers.finnhub.finnhub_client import FinnhubClient


logger = logging.getLogger(__name__)


class FinnhubMacroNewsProvider(NewsDataSource):
    """Fetches market-wide macro news from Finnhub's /news endpoint.

    Fetches general market news using ID-based pagination and maps articles to watchlist
    symbols based on the related field in each article. Falls back to 'ALL' for
    articles that don't match any watchlist symbols.

    Rate Limits:
        Free tier: 60 calls/min.
        Each poll cycle makes one call (no per-symbol iteration for macro news).
    """

    def __init__(
        self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub Macro"
    ) -> None:
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)
        self.last_fetched_max_id: int | None = None

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        min_id: int | None = None,
    ) -> list[NewsItem]:
        now_utc = datetime.now(timezone.utc)

        if min_id is None:
            buffer_time = now_utc - timedelta(days=2)
        else:
            buffer_time = None

        news_items: list[NewsItem] = []
        params: dict[str, Any] = {"category": "general"}

        if min_id is not None:
            params["minId"] = min_id

        articles = await self.client.get("/news", params)

        if not isinstance(articles, list):
            raise DataSourceError(
                f"Finnhub API returned {type(articles).__name__} instead of list"
            )

        if min_id is not None:
            filtered_articles = [
                article
                for article in articles
                if isinstance(article.get("id"), int) and article["id"] > min_id
            ]
            if len(filtered_articles) < len(articles):
                logger.debug(
                    f"Filtered {len(articles) - len(filtered_articles)} articles with id <= {min_id}"
                )
            articles = filtered_articles

        for article in articles:
            try:
                items = self._parse_article(article, buffer_time)
                news_items.extend(items)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.debug(
                    f"Failed to parse macro news article {article.get('id', 'unknown')}: {exc}"
                )
                continue
            except Exception as exc:  # pragma: no cover - unexpected
                logger.exception(
                    f"Unexpected error parsing macro news article {article.get('id', 'unknown')}: {exc}"
                )
                continue

        ids = [
            article["id"]
            for article in articles
            if isinstance(article.get("id"), int) and article["id"] > 0
        ]
        self.last_fetched_max_id = max(ids) if ids else None

        return news_items

    def _parse_article(
        self,
        article: dict[str, Any],
        buffer_time: datetime | None,
    ) -> list[NewsItem]:
        headline = article.get("headline", "").strip()
        url = article.get("url", "").strip()
        datetime_epoch = article.get("datetime", 0)

        if not headline or not url or datetime_epoch <= 0:
            return []

        try:
            published = datetime.fromtimestamp(datetime_epoch, tz=timezone.utc)
        except (ValueError, OSError) as exc:  # pragma: no cover
            logger.debug(
                f"Skipping macro news article due to invalid epoch {datetime_epoch}: {exc}"
            )
            return []

        if buffer_time and published <= buffer_time:
            return []

        related = article.get("related", "").strip()
        symbols = self._extract_symbols_from_related(related)
        source = article.get("source", "").strip() or "Finnhub"
        summary = article.get("summary", "").strip()
        content = summary if summary else None

        news_items: list[NewsItem] = []
        for symbol in symbols:
            try:
                news_item = NewsItem(
                    symbol=symbol,
                    url=url,
                    headline=headline,
                    published=published,
                    source=source,
                    content=content,
                )
                news_items.append(news_item)
            except ValueError as exc:
                logger.debug(
                    f"NewsItem validation failed for {symbol} (url={url}): {exc}"
                )
                continue

        return news_items

    def _extract_symbols_from_related(self, related: str | None) -> list[str]:
        if not related or not related.strip():
            return ["ALL"]

        symbols = parse_symbols(
            related,
            filter_to=self.symbols,
            validate=True,
            log_label="RELATED",
        )

        if not symbols:
            return ["ALL"]

        return symbols

