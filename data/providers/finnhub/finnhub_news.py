"""Company news provider implementation."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data.base import NewsDataSource
from data.models import NewsItem
from .finnhub_client import FinnhubClient


logger = logging.getLogger(__name__)


class FinnhubNewsProvider(NewsDataSource):
    """Fetches company news from Finnhub's /company-news endpoint."""

    def __init__(self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub") -> None:
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)

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
            from_date = buffer_time.date()
        else:
            from_date = (now_utc - timedelta(days=2)).date()
            buffer_time = None

        to_date = now_utc.date()
        news_items: list[NewsItem] = []

        for symbol in self.symbols:
            try:
                params = {
                    "symbol": symbol,
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                }

                articles = await self.client.get("/company-news", params)

                if not isinstance(articles, list):
                    continue

                for article in articles:
                    try:
                        news_item = self._parse_article(article, symbol, buffer_time if since else None)
                        if news_item:
                            news_items.append(news_item)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Failed to parse company news article for %s: %s", symbol, exc)
                        continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("Company news fetch failed for %s: %s", symbol, exc)
                continue

        return news_items

    def _parse_article(
        self,
        article: dict[str, Any],
        symbol: str,
        buffer_time: datetime | None,
    ) -> NewsItem | None:
        headline = article.get("headline", "").strip()
        url = article.get("url", "").strip()
        datetime_epoch = article.get("datetime", 0)

        if not headline or not url or datetime_epoch <= 0:
            return None

        try:
            published = datetime.fromtimestamp(datetime_epoch, tz=timezone.utc)
        except (ValueError, OSError) as exc:  # pragma: no cover
            logger.debug(
                "Skipping company news article for %s due to invalid epoch %s: %s",
                symbol,
                datetime_epoch,
                exc,
            )
            return None

        if buffer_time and published <= buffer_time:
            return None

        source = article.get("source", "").strip() or "Finnhub"
        summary = article.get("summary", "").strip()
        content = summary if summary else None

        try:
            return NewsItem(
                symbol=symbol,
                url=url,
                headline=headline,
                published=published,
                source=source,
                content=content,
            )
        except ValueError as exc:  # pragma: no cover
            logger.debug("NewsItem validation failed for %s (url=%s): %s", symbol, url, exc)
            return None

