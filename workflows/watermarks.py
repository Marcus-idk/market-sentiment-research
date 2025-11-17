"""Watermark planning and persistence helpers for news providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from data import NewsDataSource
from data.models import NewsEntry
from data.providers.finnhub import FinnhubMacroNewsProvider, FinnhubNewsProvider
from data.providers.polygon import PolygonMacroNewsProvider, PolygonNewsProvider
from data.storage import (
    get_last_seen_id,
    get_last_seen_timestamp,
    set_last_seen_id,
    set_last_seen_timestamp,
)
from data.storage.state_enums import Provider as ProviderEnum
from data.storage.state_enums import Scope as ScopeEnum
from data.storage.state_enums import Stream as StreamEnum

logger = logging.getLogger(__name__)


CursorKind = Literal["timestamp", "id"]


@dataclass(frozen=True)
class CursorRule:
    """Describes how a provider/stream tracks watermarks."""

    provider: ProviderEnum  # Which provider (FINNHUB, POLYGON)
    stream: StreamEnum  # Which stream (COMPANY, MACRO)
    scope: ScopeEnum  # SYMBOL = one watermark per symbol, GLOBAL = one watermark total
    cursor: CursorKind  # "timestamp" = datetime cursor, "id" = integer cursor
    bootstrap: bool  # True = detect new symbols and backfill for global scope providers
    overlap_family: Literal[
        "company", "macro"
    ]  # Which config fields to read (*_news_overlap_minutes, *_news_first_run_days)


CURSOR_RULES: dict[type[NewsDataSource], CursorRule] = {
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
}


@dataclass
class CursorPlan:
    since: datetime | None = None
    min_id: int | None = None
    symbol_since_map: dict[str, datetime] | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _cfg_days(settings: object | None, family: str, default: int = 7) -> int:
    if settings is None:
        return default
    return int(getattr(settings, f"{family}_news_first_run_days", default))


def _clamp_future(ts: datetime, now: datetime) -> datetime:
    cap = now + timedelta(seconds=60)
    return ts if ts <= cap else cap


def _is_bootstrap_symbol(
    db_path: str,
    rule: CursorRule,
    *,
    symbol: str,
    base_since: datetime,
) -> bool:
    try:
        symbol_ts = get_last_seen_timestamp(
            db_path,
            rule.provider,
            rule.stream,
            ScopeEnum.SYMBOL,
            symbol=symbol,
        )
    except Exception as exc:  # noqa: BLE001 - defensive logging for DB failures
        logger.debug("Bootstrap detection failed for %s: %s", symbol, exc)
        return False

    if symbol_ts is None:
        return True

    return _ensure_utc(symbol_ts) < base_since


@dataclass
class WatermarkEngine:
    db_path: str

    def build_plan(self, provider: NewsDataSource) -> CursorPlan:
        rule = CURSOR_RULES.get(type(provider))
        if not rule:
            logger.debug(
                f"No cursor rule defined for {type(provider).__name__}; using default cursors"
            )
            return CursorPlan()

        settings = self._get_settings(provider)
        now = _utc_now()

        if rule.cursor == "id":
            last_id = get_last_seen_id(self.db_path, rule.provider, rule.stream, rule.scope)
            return CursorPlan(min_id=last_id)

        first_run_days = _cfg_days(settings, rule.overlap_family)

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
                    since = _ensure_utc(prev)
                per_symbol_map[symbol] = since
            return CursorPlan(symbol_since_map=per_symbol_map)

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
            base_since = _ensure_utc(prev)

        symbol_map: dict[str, datetime] | None = None
        if rule.bootstrap and getattr(provider, "symbols", None):
            overrides: dict[str, datetime] = {}
            override_since = now - timedelta(days=first_run_days)
            for symbol in getattr(provider, "symbols", []) or []:
                if _is_bootstrap_symbol(
                    self.db_path,
                    rule,
                    symbol=symbol,
                    base_since=base_since,
                ):
                    overrides[symbol] = override_since
            if overrides:
                symbol_map = overrides

        return CursorPlan(since=base_since, symbol_since_map=symbol_map)

    def commit_updates(self, provider: NewsDataSource, entries: list[NewsEntry]) -> None:
        rule = CURSOR_RULES.get(type(provider))
        if not rule:
            logger.debug(
                f"Skipping watermark update for {type(provider).__name__} (no cursor rule)"
            )
            return

        now = _utc_now()

        if rule.cursor == "id":
            max_id = getattr(provider, "last_fetched_max_id", None)
            if max_id is None:
                return
            set_last_seen_id(self.db_path, rule.provider, rule.stream, rule.scope, max_id)
            return

        if not entries:
            return

        if rule.scope is ScopeEnum.SYMBOL:
            max_by_symbol: dict[str, datetime] = {}
            for entry in entries:
                if not entry.symbol:
                    continue
                published = _ensure_utc(entry.published)
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
                        ts.isoformat(),
                        clamped.isoformat(),
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

        max_ts = max(_ensure_utc(entry.published) for entry in entries)
        clamped = _clamp_future(max_ts, now)
        if clamped != max_ts:
            logger.warning(
                "Clamped future watermark provider=%s stream=%s "
                "scope=GLOBAL symbol=None original=%s clamped=%s",
                rule.provider.value,
                rule.stream.value,
                max_ts.isoformat(),
                clamped.isoformat(),
            )

        existing = get_last_seen_timestamp(
            self.db_path,
            rule.provider,
            rule.stream,
            ScopeEnum.GLOBAL,
            symbol=None,
        )
        existing_ts = _ensure_utc(existing) if existing is not None else None
        target = clamped if existing_ts is None else max(existing_ts, clamped)
        if existing_ts is None or target > existing_ts:
            set_last_seen_timestamp(
                self.db_path,
                rule.provider,
                rule.stream,
                ScopeEnum.GLOBAL,
                target,
            )

        if rule.bootstrap:
            per_symbol_max: dict[str, datetime] = {}
            for entry in entries:
                if not entry.symbol:
                    continue
                published = _ensure_utc(entry.published)
                current = per_symbol_max.get(entry.symbol)
                if current is None or published > current:
                    per_symbol_max[entry.symbol] = published

            for symbol, ts in per_symbol_max.items():
                clamped_symbol = _clamp_future(ts, now)
                existing_symbol = get_last_seen_timestamp(
                    self.db_path,
                    rule.provider,
                    rule.stream,
                    ScopeEnum.SYMBOL,
                    symbol=symbol,
                )
                existing_symbol_ts = (
                    _ensure_utc(existing_symbol) if existing_symbol is not None else None
                )
                target_symbol = (
                    clamped_symbol
                    if existing_symbol_ts is None
                    else max(existing_symbol_ts, clamped_symbol)
                )
                if existing_symbol_ts is not None and target_symbol == existing_symbol_ts:
                    continue

                set_last_seen_timestamp(
                    self.db_path,
                    rule.provider,
                    rule.stream,
                    ScopeEnum.SYMBOL,
                    target_symbol,
                    symbol=symbol,
                )

    @staticmethod
    def _get_settings(provider: NewsDataSource) -> object | None:
        settings = getattr(provider, "settings", None)
        if settings is None:
            raise RuntimeError(
                f"{type(provider).__name__} is missing required 'settings' attribute"
            )
        return settings


def is_macro_stream(provider: NewsDataSource) -> bool:
    rule = CURSOR_RULES.get(type(provider))
    return bool(rule and rule.stream is StreamEnum.MACRO)
