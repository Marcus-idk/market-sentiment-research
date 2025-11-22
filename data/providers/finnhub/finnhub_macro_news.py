"""Macro news provider implementation."""

import logging
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
from data.storage.storage_utils import _datetime_to_iso
from utils.symbols import parse_symbols

logger = logging.getLogger(__name__)


class FinnhubMacroNewsProvider(NewsDataSource):
    """Fetches macro/market news from Finnhub's /news endpoint."""

    def __init__(
        self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub Macro"
    ) -> None:
        super().__init__(source_name)
        self.settings = settings
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)
        self.last_fetched_max_id: int | None = None

    async def validate_connection(self) -> bool:
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        min_id: int | None = None,
    ) -> list[NewsEntry]:
        """Stream macro news incrementally using minId pagination."""
        now_utc = datetime.now(UTC)
        bootstrap_delta = timedelta(days=self.settings.macro_news_first_run_days)

        if min_id is None:
            buffer_time = now_utc - bootstrap_delta
        else:
            buffer_time = None

        news_entries: list[NewsEntry] = []
        base_params: dict[str, Any] = {"category": "general"}
        current_min_id = min_id
        overall_max_id: int | None = None
        reached_buffer_cutoff = False

        # Not factored into a helper like polygon_news.py, this is a global stream
        while True:
            params = base_params.copy()

            # Add min_id for pagination (first run EVER, not first loop)
            if current_min_id is not None:
                params["minId"] = current_min_id

            articles = await self.client.get("/news", params)

            if not isinstance(articles, list):
                raise DataSourceError(
                    f"Finnhub API returned {type(articles).__name__} instead of list"
                )

            # First EVER loop won't hit this block
            if current_min_id is not None:
                filtered_articles = [
                    article
                    for article in articles
                    if isinstance(article.get("id"), int) and article["id"] > current_min_id
                ]
                if len(filtered_articles) < len(articles):
                    logger.debug(
                        f"Filtered {len(articles) - len(filtered_articles)} articles "
                        f"with id <= {current_min_id}"
                    )
                articles = filtered_articles

            # Stop if no more articles (done paginating)
            if not articles:
                break

            page_ids: list[int] = []

            for article in articles:
                article_id = article.get("id")
                if isinstance(article_id, int) and article_id > 0:
                    page_ids.append(article_id)

                # First EVER run only; check if we hit buffer_time cutoff.
                # We keep processing the whole page even if we hit the cutoff.
                if buffer_time is not None:
                    published_ts = article.get("datetime")
                    if isinstance(published_ts, (int, float)):
                        try:
                            published_dt = datetime.fromtimestamp(published_ts, tz=UTC)
                        except (ValueError, OSError):
                            published_dt = None
                        if published_dt and published_dt <= buffer_time:
                            reached_buffer_cutoff = True

                try:
                    items = self._parse_article(article, buffer_time)
                    news_entries.extend(items)
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    logger.debug(
                        f"Failed to parse macro news article {article.get('id', 'unknown')}: {exc}"
                    )
                    continue

            if not page_ids:
                break

            latest_page_id = max(page_ids)
            if overall_max_id is None or latest_page_id > overall_max_id:
                overall_max_id = latest_page_id

            if reached_buffer_cutoff:
                break

            previous_min_id = current_min_id
            current_min_id = latest_page_id
            if previous_min_id is not None and latest_page_id <= previous_min_id:
                break

        self.last_fetched_max_id = overall_max_id

        return news_entries

    def _parse_article(
        self,
        article: dict[str, Any],
        buffer_time: datetime | None,
    ) -> list[NewsEntry]:
        """Parse Finnhub macro news article into one or more NewsEntry objects."""
        headline = article.get("headline", "").strip()
        url = article.get("url", "").strip()
        datetime_epoch = article.get("datetime", 0)

        if not headline or not url or datetime_epoch <= 0:
            return []

        try:
            published = datetime.fromtimestamp(datetime_epoch, tz=UTC)
        except (ValueError, OSError) as exc:
            logger.debug(
                f"Skipping macro news article due to invalid epoch {datetime_epoch}: {exc}"
            )
            # Return empty array because function might map to multiple entries
            return []

        # Drop this article if it's older than the bootstrap/lookback cutoff
        if buffer_time and published <= buffer_time:
            cutoff_iso = _datetime_to_iso(buffer_time)
            logger.warning(
                f"Finnhub API returned article with published={published.isoformat()} "
                f"at/before cutoff {cutoff_iso} despite default lookback window"
            )
            return []

        related = article.get("related", "").strip()
        symbols = self._extract_symbols_from_related(related)
        source = article.get("source", "").strip() or "Finnhub"
        summary = article.get("summary", "").strip()
        content = summary if summary else None

        entries: list[NewsEntry] = []
        try:
            article_model = NewsItem(
                url=url,
                headline=headline,
                published=published,
                source=source,
                news_type=NewsType.MACRO,
                content=content,
            )
        except ValueError as exc:
            logger.debug(f"NewsItem validation failed (url={url}): {exc}")
            return []
        for symbol in symbols:
            try:
                entries.append(NewsEntry(article=article_model, symbol=symbol, is_important=None))
            except ValueError as exc:
                logger.debug(f"NewsEntry validation failed for {symbol} (url={url}): {exc}")
                continue

        return entries

    def _extract_symbols_from_related(self, related: str | None) -> list[str]:
        """Parse Finnhub related string into watchlisted symbols."""
        if not related or not related.strip():
            return ["MARKET"]

        symbols = parse_symbols(
            related,
            filter_to=self.symbols,
            validate=True,
        )

        if not symbols:
            return ["MARKET"]

        return symbols
