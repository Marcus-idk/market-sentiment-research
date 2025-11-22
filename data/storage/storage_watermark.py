"""Typed CRUD helpers for the `last_seen_state` table."""

from __future__ import annotations

import logging
from datetime import datetime

from data.storage.db_context import _cursor_context
from data.storage.state_enums import Provider, Scope, Stream
from data.storage.storage_utils import _datetime_to_iso, _iso_to_datetime

_GLOBAL_SYMBOL_SENTINEL = "__GLOBAL__"

logger = logging.getLogger(__name__)


def _normalize_symbol(scope: Scope, symbol: str | None) -> str | None:
    """Normalize symbol requirements based on scope."""

    if scope is Scope.SYMBOL:
        if symbol is None:
            raise ValueError("symbol is required when scope is Scope.SYMBOL")
        stripped = symbol.strip()
        if not stripped:
            raise ValueError("symbol cannot be empty when scope is Scope.SYMBOL")
        if stripped == _GLOBAL_SYMBOL_SENTINEL:
            raise ValueError(f"symbol '{_GLOBAL_SYMBOL_SENTINEL}' reserved for internal use")
        return stripped

    if symbol is not None and symbol.strip():
        normalized = symbol.strip()
        if normalized != _GLOBAL_SYMBOL_SENTINEL:
            raise ValueError("symbol must be None when scope is Scope.GLOBAL")
        return _GLOBAL_SYMBOL_SENTINEL

    return _GLOBAL_SYMBOL_SENTINEL


def _fetch_state_row(
    db_path: str,
    provider: Provider,
    stream: Stream,
    scope: Scope,
    symbol: str | None,
) -> dict[str, str | int | None] | None:
    """Fetch raw watermark row matching provider/stream/scope/symbol."""
    normalized_symbol = _normalize_symbol(scope, symbol)

    query = """
        SELECT timestamp, id
        FROM last_seen_state
        WHERE provider = ? AND stream = ? AND scope = ?
              AND symbol = ?
    """

    base = (provider.value, stream.value, scope.value)
    params = (*base, normalized_symbol)

    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def _upsert_state(
    db_path: str,
    provider: Provider,
    stream: Stream,
    scope: Scope,
    *,
    timestamp: str | None,
    cursor_id: int | None,
    symbol: str | None,
) -> None:
    """Insert or update watermark row for provider/stream/scope/symbol."""
    normalized_symbol = _normalize_symbol(scope, symbol)

    with _cursor_context(db_path) as cursor:
        cursor.execute(
            """
            INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, stream, scope, symbol)
            DO UPDATE SET timestamp = excluded.timestamp, id = excluded.id
            """,
            (
                provider.value,
                stream.value,
                scope.value,
                normalized_symbol,
                timestamp,
                cursor_id,
            ),
        )


def get_last_seen_timestamp(
    db_path: str,
    provider: Provider,
    stream: Stream,
    scope: Scope,
    symbol: str | None = None,
) -> datetime | None:
    """Read the timestamp watermark for the specified provider/stream/scope."""

    row = _fetch_state_row(db_path, provider, stream, scope, symbol)
    stored_value = row["timestamp"] if row else None
    if stored_value is None:
        return None
    try:
        return _iso_to_datetime(str(stored_value))
    except (TypeError, ValueError) as exc:
        logger.debug(
            "Invalid timestamp watermark provider=%s stream=%s scope=%s symbol=%s: %s",
            provider.value,
            stream.value,
            scope.value,
            symbol,
            exc,
        )
        return None


def set_last_seen_timestamp(
    db_path: str,
    provider: Provider,
    stream: Stream,
    scope: Scope,
    timestamp: datetime,
    symbol: str | None = None,
) -> None:
    """Persist a timestamp watermark for the provider/stream/scope tuple."""

    iso_value = _datetime_to_iso(timestamp)
    _upsert_state(
        db_path,
        provider,
        stream,
        scope,
        timestamp=iso_value,
        cursor_id=None,
        symbol=symbol,
    )


def get_last_seen_id(
    db_path: str,
    provider: Provider,
    stream: Stream,
    scope: Scope,
    symbol: str | None = None,
) -> int | None:
    """Read the ID watermark for the specified provider/stream/scope."""

    row = _fetch_state_row(db_path, provider, stream, scope, symbol)
    stored_value = row["id"] if row else None
    if stored_value is None:
        return None
    try:
        return int(stored_value)
    except (TypeError, ValueError) as exc:
        logger.debug(
            "Invalid id watermark provider=%s stream=%s scope=%s symbol=%s: %s",
            provider.value,
            stream.value,
            scope.value,
            symbol,
            exc,
        )
        return None


def set_last_seen_id(
    db_path: str,
    provider: Provider,
    stream: Stream,
    scope: Scope,
    id_value: int,
    symbol: str | None = None,
) -> None:
    """Persist an ID watermark for the provider/stream/scope tuple."""

    _upsert_state(
        db_path,
        provider,
        stream,
        scope,
        timestamp=None,
        cursor_id=id_value,
        symbol=symbol,
    )
