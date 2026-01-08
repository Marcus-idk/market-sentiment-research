"""Reddit social sentiment provider."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from prawcore import exceptions as praw_exceptions

from config.providers.reddit import RedditSettings
from data.base import SocialDataSource
from data.models import SocialDiscussion
from data.providers.reddit.reddit_client import RedditClient
from utils.datetime_utils import epoch_seconds_to_utc_datetime
from utils.symbols import normalize_symbol_list

logger = logging.getLogger(__name__)


class RedditSocialProvider(SocialDataSource):
    """Fetches Reddit posts and top comments for tracked symbols."""

    SUBREDDITS = "stocks+investing+wallstreetbets"
    SOURCE = "reddit"

    def __init__(
        self, settings: RedditSettings, symbols: list[str], source_name: str = "Reddit"
    ) -> None:
        """Initialize the Reddit social provider."""
        super().__init__(source_name)
        self.settings = settings
        self.symbols = normalize_symbol_list(symbols)
        self.client = RedditClient(settings)

    async def validate_connection(self) -> bool:
        """Return True when Reddit API credentials are valid."""
        # PRAW is synchronous - wrap in thread
        return await asyncio.to_thread(self.client.validate_connection)

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        symbol_since_map: Mapping[str, datetime] | None = None,
    ) -> list[SocialDiscussion]:
        """Fetch Reddit discussions for tracked symbols using incremental cursors."""
        if not self.symbols:
            return []

        now_utc = datetime.now(UTC)
        overlap_delta = timedelta(minutes=self.settings.social_news_overlap_minutes)
        bootstrap_delta = timedelta(days=self.settings.social_news_first_run_days)

        discussions: list[SocialDiscussion] = []

        for symbol in self.symbols:
            # Prefer per-symbol cursor; fall back to global since
            symbol_cursor = self._resolve_symbol_cursor(symbol, symbol_since_map, since)
            if symbol_cursor is not None:
                start_time = symbol_cursor - overlap_delta
                time_filter = self.settings.incremental_time_filter
            else:
                start_time = now_utc - bootstrap_delta
                time_filter = self.settings.bootstrap_time_filter

            if start_time > now_utc:
                start_time = now_utc

            try:
                symbol_items = await asyncio.to_thread(
                    self._fetch_symbol, symbol, start_time, time_filter
                )
                discussions.extend(symbol_items)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.warning("Reddit fetch failed for %s: %s", symbol, exc)
                continue
            except praw_exceptions.PrawcoreException as exc:
                logger.warning("Reddit API error for %s: %s", symbol, exc)
                continue

        return discussions

    def _resolve_symbol_cursor(
        self,
        symbol: str,
        symbol_since_map: Mapping[str, datetime] | None,
        global_since: datetime | None,
    ) -> datetime | None:
        """Return per-symbol cursor when available, else fall back to global."""
        # NOTE: Duplicated in other providers; consider extracting a shared helper
        # (e.g., in data/base.py).
        if symbol_since_map is not None and symbol in symbol_since_map:
            return symbol_since_map[symbol]
        return global_since

    def _fetch_symbol(
        self, symbol: str, start_time: datetime, time_filter: str
    ) -> list[SocialDiscussion]:
        """Search Reddit for posts mentioning the symbol and parse into discussions."""
        subreddit_combo = self.client.reddit.subreddit(self.SUBREDDITS)
        try:
            search_results = subreddit_combo.search(
                query=symbol,
                sort="new",
                time_filter=time_filter,
                limit=self.settings.search_limit,
            )
        except (
            praw_exceptions.PrawcoreException,
            AttributeError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            logger.warning("Reddit search failed for %s: %s", symbol, exc)
            return []

        discussions: list[SocialDiscussion] = []

        for submission in search_results:
            try:
                discussion = self._parse_submission(submission, symbol, start_time)
                if discussion:
                    discussions.append(discussion)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.debug(
                    "Failed to parse Reddit submission for %s (id=%s): %s",
                    symbol,
                    getattr(submission, "id", "unknown"),
                    exc,
                )
                continue

        return discussions

    def _parse_submission(
        self, submission: Any, symbol: str, start_time: datetime
    ) -> SocialDiscussion | None:
        """Parse a Reddit submission into a SocialDiscussion, returning None if invalid."""
        created_utc = getattr(submission, "created_utc", None)
        if created_utc is None:
            logger.debug(
                "Submission missing created_utc for %s (id=%s)",
                symbol,
                getattr(submission, "id", "unknown"),
            )
            return None

        try:
            # defensive conversion float()
            published = epoch_seconds_to_utc_datetime(float(created_utc))
        except (ValueError, OSError, OverflowError, TypeError) as exc:
            submission_id = getattr(submission, "id", "unknown")
            logger.debug(
                "Failed to parse timestamp %r for submission %s: %s",
                created_utc,
                submission_id,
                exc,
            )
            return None

        if published <= start_time:
            return None

        title = (getattr(submission, "title", "") or "").strip()
        if not title:
            logger.debug(
                "Submission missing title for %s (id=%s)",
                symbol,
                getattr(submission, "id", "unknown"),
            )
            return None

        subreddit_obj = getattr(submission, "subreddit", None)
        subreddit_name = ""
        if subreddit_obj is not None:
            subreddit_name = getattr(subreddit_obj, "display_name", "") or str(subreddit_obj)
        subreddit_name = (subreddit_name or "").strip()
        if not subreddit_name:
            logger.debug(
                "Submission missing subreddit for %s (id=%s)",
                symbol,
                getattr(submission, "id", "unknown"),
            )
            return None

        permalink = (getattr(submission, "permalink", "") or "").strip()
        url = permalink
        if url and not url.startswith("http"):
            url = f"https://www.reddit.com{url}"
        if not url:
            fallback_url = (getattr(submission, "url", "") or "").strip()
            if fallback_url.startswith("http"):
                url = fallback_url
            else:
                logger.debug(
                    "Submission missing valid URL for %s (id=%s)",
                    symbol,
                    getattr(submission, "id", "unknown"),
                )
                return None

        source_id = (getattr(submission, "name", "") or "").strip()
        if not source_id:
            submission_id = (getattr(submission, "id", "") or "").strip()
            if not submission_id:
                logger.debug("Submission missing both name and id fields for %s", symbol)
                return None
            source_id = f"t3_{submission_id}"

        content = self._build_content(submission)

        return SocialDiscussion(
            source=self.SOURCE,
            source_id=source_id,
            symbol=symbol,
            community=subreddit_name,
            title=title,
            url=url,
            published=published,
            content=content,
        )

    def _build_content(self, submission: Any) -> str | None:
        """Concatenate post selftext and top comments; tolerant of comment fetch failures."""
        base_text = (getattr(submission, "selftext", "") or "").strip()
        comments_text: list[str] = []

        try:
            submission.comment_sort = "top"
            submission.comment_limit = self.settings.comments_limit
            submission.comments.replace_more(limit=0)
            for comment in submission.comments[: self.settings.comments_limit]:
                body = (getattr(comment, "body", "") or "").strip()
                if body:
                    comments_text.append(body)
        except (
            praw_exceptions.PrawcoreException,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            logger.debug(
                "Failed to fetch comments for submission %s: %s",
                getattr(submission, "id", ""),
                exc,
            )

        if not base_text and not comments_text:
            return None

        content_parts: list[str] = []
        if base_text:
            content_parts.append(f"Post: {base_text}")
        if comments_text:
            content_parts.append("Comments:")
            content_parts.extend(comments_text)

        return "\n\n".join(content_parts)
