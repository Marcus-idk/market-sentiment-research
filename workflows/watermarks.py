"""Watermark planning and persistence helpers for news providers."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from data import NewsDataSource, SocialDataSource
from data.models import NewsEntry, SocialDiscussion
from data.providers.finnhub import FinnhubMacroNewsProvider, FinnhubNewsProvider
from data.providers.polygon import PolygonMacroNewsProvider, PolygonNewsProvider
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

    provider: ProviderEnum  # Which provider (FINNHUB, POLYGON)
    stream: StreamEnum  # Which stream (COMPANY, MACRO)
    scope: ScopeEnum  # SYMBOL = one watermark per symbol, GLOBAL = one watermark total
    cursor: Literal["timestamp", "id"]  # "timestamp" = datetime cursor, "id" = integer cursor
    bootstrap: bool  # True = detect new symbols and backfill for global scope providers
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
        bootstrap=False,  # Auto-detects new symbols (None watermark)
        overlap_family="company",
    ),
    # Finnhub macro: one ID for all macro news
    FinnhubMacroNewsProvider: CursorRule(
        provider=ProviderEnum.FINNHUB,
        stream=StreamEnum.MACRO,
        scope=ScopeEnum.GLOBAL,  # One watermark total
        cursor="id",  # Uses integer IDs, not timestamps
        bootstrap=False,  # N/A for macro news
        overlap_family="macro",
    ),
    # Polygon company: one timestamp shared, but override for new symbols
    PolygonNewsProvider: CursorRule(
        provider=ProviderEnum.POLYGON,
        stream=StreamEnum.COMPANY,
        scope=ScopeEnum.GLOBAL,  # One watermark shared by all symbols
        cursor="timestamp",
        bootstrap=True,  # Must explicitly detect and backfill new symbols
        overlap_family="company",
    ),
    # Polygon macro: one timestamp for all macro news
    PolygonMacroNewsProvider: CursorRule(
        provider=ProviderEnum.POLYGON,
        stream=StreamEnum.MACRO,
        scope=ScopeEnum.GLOBAL,  # One watermark total
        cursor="timestamp",
        bootstrap=False,  # N/A for macro news
        overlap_family="macro",
    ),
    # Reddit social: one timestamp per symbol
    RedditSocialProvider: CursorRule(
        provider=ProviderEnum.REDDIT,
        stream=StreamEnum.SOCIAL,
        scope=ScopeEnum.SYMBOL,
        cursor="timestamp",
        bootstrap=False,
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


def _is_global_bootstrap_symbol(
    db_path: str,
    rule: CursorRule,
    *,
    symbol: str,
    base_since: datetime,
) -> bool:
    """Return True when a GLOBAL-scope provider should bootstrap this symbol.

    Notes:
        Used only for providers that use GLOBAL scope + bootstrap=True
        (e.g., Polygon company news). For per-symbol scope providers
        (e.g., Finnhub company news), bootstrap behavior is handled
        directly in build_plan.
    """
    try:
        symbol_ts = get_last_seen_timestamp(
            db_path,
            rule.provider,
            rule.stream,
            ScopeEnum.SYMBOL,
            symbol=symbol,
        )
    except (sqlite3.Error, OSError) as exc:
        logger.debug("Bootstrap detection failed for %s: %s", symbol, exc)
        return False

    if symbol_ts is None:
        return True

    return normalize_to_utc(symbol_ts) < base_since


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
            - GLOBAL+bootstrap providers (e.g., Polygon company) may return
              ``symbol_since_map`` overrides for newly added/stale symbols.
        """
        rule = CURSOR_RULES.get(type(provider))
        if not rule:
            logger.debug(
                f"No cursor rule defined for {type(provider).__name__}; using default cursors"
            )
            return CursorPlan()

        # Provider-specific settings (used for first-run windows, etc.).
        settings = self._get_settings(provider)
        now = _utc_now()

        # ID-based cursor: only track the last integer ID.
        if rule.cursor == "id":
            last_id = get_last_seen_id(self.db_path, rule.provider, rule.stream, rule.scope)
            return CursorPlan(min_id=last_id)

        # Timestamp-based cursor: derive "first run" window from settings.
        first_run_days = _cfg_days(settings, rule.overlap_family)

        # Per-symbol scope (e.g., Finnhub company news): one cursor per symbol.
        if rule.scope is ScopeEnum.SYMBOL:
            per_symbol_map: dict[str, datetime] = {}
            for symbol in getattr(provider, "symbols", []) or []:
                prev = get_last_seen_timestamp(
                    self.db_path,
                    rule.provider,
                    rule.stream,
                    ScopeEnum.SYMBOL,
                    symbol=symbol,
                )
                if prev is None:
                    since = now - timedelta(days=first_run_days)
                else:
                    since = normalize_to_utc(prev)
                per_symbol_map[symbol] = since
            return CursorPlan(symbol_since_map=per_symbol_map)

        # Global scope (e.g., Polygon company/macro): single shared cursor.
        prev = get_last_seen_timestamp(
            self.db_path,
            rule.provider,
            rule.stream,
            ScopeEnum.GLOBAL,
            symbol=None,
        )
        if prev is None:
            base_since = now - timedelta(days=first_run_days)
        else:
            base_since = normalize_to_utc(prev)

        # Optional per-symbol bootstrap overrides for GLOBAL+bootstrap providers
        # (e.g., Polygon company news): new/stale symbols get a custom window.
        symbol_map: dict[str, datetime] | None = None
        if rule.bootstrap and getattr(provider, "symbols", None):
            overrides: dict[str, datetime] = {}
            override_since = now - timedelta(days=first_run_days)
            for symbol in getattr(provider, "symbols", []) or []:
                if _is_global_bootstrap_symbol(
                    self.db_path,
                    rule,
                    symbol=symbol,
                    base_since=base_since,
                ):
                    overrides[symbol] = override_since
            if overrides:
                symbol_map = overrides

        return CursorPlan(since=base_since, symbol_since_map=symbol_map)

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
            logger.debug(
                f"Skipping watermark update for {type(provider).__name__} (no cursor rule)"
            )
            return

        # Capture "now" once so all clamping uses the same reference.
        now = _utc_now()

        # ID-based cursor: rely on provider's recorded max ID.
        if rule.cursor == "id":
            max_id = getattr(provider, "last_fetched_max_id", None)
            if max_id is None:
                return
            set_last_seen_id(self.db_path, rule.provider, rule.stream, rule.scope, max_id)
            return

        # No entries means nothing to advance for timestamp-based cursors.
        if not entries:
            return

        # Per-symbol scope (e.g., Finnhub company): track max timestamp per symbol.
        if rule.scope is ScopeEnum.SYMBOL:
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
            return

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

        if rule.bootstrap:
            per_symbol_max: dict[str, datetime] = {}
            for entry in entries:
                if not entry.symbol:
                    continue
                published = normalize_to_utc(entry.published)
                current = per_symbol_max.get(entry.symbol)
                if current is None or published > current:
                    per_symbol_max[entry.symbol] = published

            for symbol, ts in per_symbol_max.items():
                clamped_symbol = _clamp_future(ts, now)
                # SQL upsert is monotonic - only advances forward
                set_last_seen_timestamp(
                    self.db_path,
                    rule.provider,
                    rule.stream,
                    ScopeEnum.SYMBOL,
                    clamped_symbol,
                    symbol=symbol,
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
