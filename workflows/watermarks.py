"""Watermark planning and persistence helpers for news providers."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from data import NewsDataSource, SocialDataSource
from data.models import NewsEntry, SocialDiscussion
from data.providers.finnhub import FinnhubMacroNewsProvider, FinnhubNewsProvider
from data.providers.reddit import RedditSocialProvider
from data.storage import (
    get_last_seen_id,
    get_last_seen_timestamp,
    set_last_seen_id,
    set_last_seen_timestamp,
)
from data.storage.state_enums import Provider as ProviderEnum
from data.storage.state_enums import Scope as ScopeEnum
from data.storage.state_enums import Stream as StreamEnum
from data.storage.storage_utils import _datetime_to_iso
from utils.datetime_utils import normalize_to_utc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CursorRule:
    """Describes how a provider/stream tracks watermarks."""

    provider: ProviderEnum  # Which provider (e.g., FINNHUB, REDDIT)
    stream: StreamEnum  # Which stream (COMPANY, MACRO)
    scope: ScopeEnum  # SYMBOL = one watermark per symbol, GLOBAL = one watermark total
    cursor: Literal["timestamp", "id"]  # "timestamp" = datetime cursor, "id" = integer cursor
    overlap_family: Literal[
        "company", "macro", "social"
    ]  # Which config fields to read (*_news_overlap_minutes, *_news_first_run_days)


CURSOR_RULES: dict[type[NewsDataSource | SocialDataSource], CursorRule] = {
    # Finnhub company: one timestamp per symbol (AAPL, TSLA each tracked separately)
    FinnhubNewsProvider: CursorRule(
        provider=ProviderEnum.FINNHUB,
        stream=StreamEnum.COMPANY,
        scope=ScopeEnum.SYMBOL,  # Per-symbol watermarks
        cursor="timestamp",
        overlap_family="company",
    ),
    # Finnhub macro: one ID for all macro news
    FinnhubMacroNewsProvider: CursorRule(
        provider=ProviderEnum.FINNHUB,
        stream=StreamEnum.MACRO,
        scope=ScopeEnum.GLOBAL,  # One watermark total
        cursor="id",  # Uses integer IDs, not timestamps
        overlap_family="macro",
    ),
    # Reddit social: one timestamp per symbol
    RedditSocialProvider: CursorRule(
        provider=ProviderEnum.REDDIT,
        stream=StreamEnum.SOCIAL,
        scope=ScopeEnum.SYMBOL,
        cursor="timestamp",
        overlap_family="social",
    ),
}


@dataclass(frozen=True)
class CursorPlan:
    """Hold cursor inputs for incremental fetches."""

    since: datetime | None = None
    min_id: int | None = None
    symbol_since_map: dict[str, datetime] | None = None


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def _cfg_days(settings: object | None, family: str, default: int = 7) -> int:
    """Read first-run day window from settings, falling back to default."""
    if settings is None:
        return default
    return int(getattr(settings, f"{family}_news_first_run_days", default))


def _clamp_future(ts: datetime, now: datetime) -> datetime:
    """Clamp a timestamp to at most 60 seconds in the future."""
    cap = now + timedelta(seconds=60)
    return ts if ts <= cap else cap


@dataclass
class WatermarkEngine:
    """Build fetch plans and persist provider watermarks."""

    db_path: str

    def build_plan(self, provider: NewsDataSource | SocialDataSource) -> CursorPlan:
        """Build cursor plan using first-run lookbacks and stored watermarks.

        Notes:
            - First run: uses ``*_news_first_run_days`` from the provider settings.
            - Overlap: providers apply ``*_news_overlap_minutes`` when fetching; the plan
              returns base cursor positions (watermark values) only.
        """
        rule = CURSOR_RULES.get(type(provider))
        if not rule:
            logger.warning(
                "No cursor rule defined for %s; using default cursors",
                type(provider).__name__,
            )
            return CursorPlan()

        # Provider-specific settings (used for first-run windows, etc.).
        settings = self._get_settings(provider)
        now = _utc_now()

        # ID-based cursor: only track the last integer ID.
        if rule.cursor == "id":
            return self._plan_id_cursor(rule)

        # Timestamp-based cursor: derive "first run" window from settings.
        first_run_days = _cfg_days(settings, rule.overlap_family)

        # Per-symbol scope (e.g., Finnhub company news): one cursor per symbol.
        if rule.scope is ScopeEnum.SYMBOL:
            return self._plan_symbol_timestamps(rule, provider, now, first_run_days)

        # Global scope: single shared cursor.
        base_since = self._plan_global_timestamp(rule, now, first_run_days)
        return CursorPlan(since=base_since)

    def _plan_id_cursor(self, rule: CursorRule) -> CursorPlan:
        """Build an ID-based cursor plan from the stored watermark."""
        last_id = get_last_seen_id(self.db_path, rule.provider, rule.stream, rule.scope)
        return CursorPlan(min_id=last_id)

    def _plan_symbol_timestamps(
        self,
        rule: CursorRule,
        provider: NewsDataSource | SocialDataSource,
        now: datetime,
        first_run_days: int,
    ) -> CursorPlan:
        """Build per-symbol timestamp cursors using stored watermarks."""
        per_symbol_map: dict[str, datetime] = {}
        is_reddit_social = rule.provider is ProviderEnum.REDDIT and rule.stream is StreamEnum.SOCIAL
        for symbol in getattr(provider, "symbols", []) or []:
            prev = get_last_seen_timestamp(
                self.db_path,
                rule.provider,
                rule.stream,
                ScopeEnum.SYMBOL,
                symbol=symbol,
            )

            # Reddit: missing cursor triggers bootstrap time_filter.
            if prev is None:
                if is_reddit_social:
                    continue
                per_symbol_map[symbol] = now - timedelta(days=first_run_days)
                continue

            per_symbol_map[symbol] = normalize_to_utc(prev)
        return CursorPlan(symbol_since_map=per_symbol_map)

    def _plan_global_timestamp(
        self,
        rule: CursorRule,
        now: datetime,
        first_run_days: int,
    ) -> datetime:
        """Return the global timestamp cursor, falling back to first-run window."""
        prev = get_last_seen_timestamp(
            self.db_path,
            rule.provider,
            rule.stream,
            ScopeEnum.GLOBAL,
            symbol=None,
        )
        if prev is None:
            return now - timedelta(days=first_run_days)
        return normalize_to_utc(prev)

    def commit_updates(
        self,
        provider: NewsDataSource | SocialDataSource,
        entries: Sequence[NewsEntry | SocialDiscussion],
    ) -> None:
        """Persist updated watermarks; ID streams use ``last_fetched_max_id``.

        Notes:
            ID-based streams (Finnhub macro) advance using the provider's
            ``last_fetched_max_id`` field.
        """
        rule = CURSOR_RULES.get(type(provider))
        if not rule:
            logger.warning(
                "Skipping watermark update for %s (no cursor rule)",
                type(provider).__name__,
            )
            return

        # Capture "now" once so all clamping uses the same reference.
        now = _utc_now()

        # ID-based cursor: rely on provider's recorded max ID.
        if rule.cursor == "id":
            self._commit_id_cursor(rule, provider)
            return

        # No entries means nothing to advance for timestamp-based cursors.
        if not entries:
            return

        # Per-symbol scope (e.g., Finnhub company): track max timestamp per symbol.
        if rule.scope is ScopeEnum.SYMBOL:
            self._commit_symbol_timestamp_updates(rule, entries, now)
            return

        self._commit_global_timestamp_update(rule, entries, now)

    def _commit_id_cursor(
        self,
        rule: CursorRule,
        provider: NewsDataSource | SocialDataSource,
    ) -> None:
        """Persist the provider's max fetched ID watermark when available."""
        max_id = getattr(provider, "last_fetched_max_id", None)
        if max_id is None:
            return
        set_last_seen_id(self.db_path, rule.provider, rule.stream, rule.scope, max_id)

    def _commit_symbol_timestamp_updates(
        self,
        rule: CursorRule,
        entries: Sequence[NewsEntry | SocialDiscussion],
        now: datetime,
    ) -> None:
        """Persist per-symbol max published timestamps, clamping future values."""
        max_by_symbol: dict[str, datetime] = {}
        for entry in entries:
            if not entry.symbol:
                continue
            published = normalize_to_utc(entry.published)
            current = max_by_symbol.get(entry.symbol)
            if current is None or published > current:
                max_by_symbol[entry.symbol] = published

        for symbol, ts in max_by_symbol.items():
            clamped = _clamp_future(ts, now)
            if clamped != ts:
                logger.warning(
                    "Clamped future watermark provider=%s stream=%s "
                    "scope=SYMBOL symbol=%s original=%s clamped=%s",
                    rule.provider.value,
                    rule.stream.value,
                    symbol,
                    _datetime_to_iso(ts),
                    _datetime_to_iso(clamped),
                )
            set_last_seen_timestamp(
                self.db_path,
                rule.provider,
                rule.stream,
                ScopeEnum.SYMBOL,
                clamped,
                symbol=symbol,
            )

    def _commit_global_timestamp_update(
        self,
        rule: CursorRule,
        entries: Sequence[NewsEntry | SocialDiscussion],
        now: datetime,
    ) -> None:
        """Persist the global max published timestamp, clamping future values."""
        max_ts = max(normalize_to_utc(entry.published) for entry in entries)
        clamped = _clamp_future(max_ts, now)
        if clamped != max_ts:
            logger.warning(
                "Clamped future watermark provider=%s stream=%s "
                "scope=GLOBAL symbol=None original=%s clamped=%s",
                rule.provider.value,
                rule.stream.value,
                _datetime_to_iso(max_ts),
                _datetime_to_iso(clamped),
            )

        # SQL upsert is monotonic - only advances forward, so no need to read first
        set_last_seen_timestamp(
            self.db_path,
            rule.provider,
            rule.stream,
            ScopeEnum.GLOBAL,
            clamped,
        )

    @staticmethod
    def _get_settings(provider: NewsDataSource | SocialDataSource) -> object | None:
        """Retrieve provider settings object or raise if missing."""
        settings = getattr(provider, "settings", None)
        if settings is None:
            raise RuntimeError(
                f"{type(provider).__name__} is missing required 'settings' attribute"
            )
        return settings


def is_macro_stream(provider: NewsDataSource | SocialDataSource) -> bool:
    """Return True when the provider handles macro news streams."""
    rule = CURSOR_RULES.get(type(provider))
    return bool(rule and rule.stream is StreamEnum.MACRO)
