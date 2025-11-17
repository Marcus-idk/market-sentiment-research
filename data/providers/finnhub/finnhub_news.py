"""Company news provider implementation."""

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
from utils.retry import RetryableError

logger = logging.getLogger(__name__)


class FinnhubNewsProvider(NewsDataSource):
    """Fetches company news from Finnhub's /company-news endpoint."""

    def __init__(
        self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub"
    ) -> None:
        super().__init__(source_name)
        self.settings = settings
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)

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
        to_date = now_utc.date()
        news_entries: list[NewsEntry] = []

        for symbol in self.symbols:
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
                        entry = self._parse_article(article, symbol, buffer_time)
                        if entry:
                            news_entries.append(entry)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        logger.debug(f"Failed to parse company news article for {symbol}: {exc}")
                        continue
            except DataSourceError:
                raise
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

    def _parse_article(
        self,
        article: dict[str, Any],
        symbol: str,
        buffer_time: datetime | None,
    ) -> NewsEntry | None:
        headline = article.get("headline", "").strip()
        url = article.get("url", "").strip()
        datetime_epoch = article.get("datetime", 0)

        if not headline or not url or datetime_epoch <= 0:
            return None

        try:
            published = datetime.fromtimestamp(datetime_epoch, tz=UTC)
        except (ValueError, OSError) as exc:
            logger.debug(
                f"Skipping company news article for {symbol} due to invalid epoch "
                f"{datetime_epoch}: {exc}"
            )
            return None

        if buffer_time and published <= buffer_time:
            logger.warning(
                f"Finnhub API returned article with published={published.isoformat()} "
                f"at/before cutoff {_datetime_to_iso(buffer_time)} despite from/to date filter"
            )
            return None

        source = article.get("source", "").strip() or "Finnhub"
        summary = article.get("summary", "").strip()
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
            logger.debug(f"NewsItem validation failed for {symbol} (url={url}): {exc}")
            return None
