"""Typed watermark storage helpers for last_seen_state."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from data.storage.db_context import _cursor_context
from data.storage.state_enums import Provider, Scope, Stream
from data.storage.storage_watermark import (
    _normalize_symbol,
    get_last_seen_id,
    get_last_seen_timestamp,
    set_last_seen_id,
    set_last_seen_timestamp,
)


class TestTimestampCursors:
    """Timestamp helpers persist and round-trip values."""

    def test_global_timestamp_roundtrip(self, temp_db):
        timestamp = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

        set_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.MACRO,
            Scope.GLOBAL,
            timestamp,
        )

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute(
                """
                SELECT provider, stream, scope, symbol, timestamp, id
                FROM last_seen_state
                WHERE provider=? AND stream=? AND scope=?
                """,
                (Provider.FINNHUB.value, Stream.MACRO.value, Scope.GLOBAL.value),
            )
            row = cursor.fetchone()
            assert row["symbol"] == "__GLOBAL__"
            assert row["timestamp"] == "2024-01-15T12:00:00Z"
            assert row["id"] is None

        roundtrip = get_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.MACRO,
            Scope.GLOBAL,
        )
        assert roundtrip is not None
        assert roundtrip == timestamp
        assert roundtrip.tzinfo is UTC

    def test_symbol_timestamp_roundtrip(self, temp_db):
        base = datetime(2024, 2, 1, 9, 30, tzinfo=UTC)
        aapl = base
        tsla = base.replace(hour=10)

        set_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.COMPANY,
            Scope.SYMBOL,
            aapl,
            symbol="AAPL",
        )
        set_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.COMPANY,
            Scope.SYMBOL,
            tsla,
            symbol="TSLA",
        )

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute(
                """
                SELECT symbol, timestamp FROM last_seen_state
                WHERE provider=? AND stream=? AND scope=?
                ORDER BY symbol
                """,
                (Provider.FINNHUB.value, Stream.COMPANY.value, Scope.SYMBOL.value),
            )
            rows = cursor.fetchall()
            assert [(row["symbol"], row["timestamp"]) for row in rows] == [
                ("AAPL", "2024-02-01T09:30:00Z"),
                ("TSLA", "2024-02-01T10:30:00Z"),
            ]

        assert (
            get_last_seen_timestamp(
                temp_db,
                Provider.FINNHUB,
                Stream.COMPANY,
                Scope.SYMBOL,
                symbol="AAPL",
            )
            == aapl
        )
        assert (
            get_last_seen_timestamp(
                temp_db,
                Provider.FINNHUB,
                Stream.COMPANY,
                Scope.SYMBOL,
                symbol="TSLA",
            )
            == tsla
        )


class TestSymbolNormalization:
    """_normalize_symbol enforces scope-specific requirements."""

    def test_symbol_scope_requires_non_empty_value(self):
        with pytest.raises(ValueError, match="symbol is required"):
            _normalize_symbol(Scope.SYMBOL, None)

        with pytest.raises(ValueError, match="cannot be empty"):
            _normalize_symbol(Scope.SYMBOL, "  ")

        with pytest.raises(ValueError, match="reserved"):
            _normalize_symbol(Scope.SYMBOL, "__GLOBAL__")

    def test_global_scope_rejects_symbols(self):
        assert _normalize_symbol(Scope.GLOBAL, None) == "__GLOBAL__"

        with pytest.raises(ValueError, match="symbol must be None"):
            _normalize_symbol(Scope.GLOBAL, "AAPL")


class TestIdCursors:
    """ID helpers store integers and guard against corruption."""

    def test_global_id_roundtrip(self, temp_db):
        set_last_seen_id(
            temp_db,
            Provider.FINNHUB,
            Stream.MACRO,
            Scope.GLOBAL,
            12345,
        )

        assert (
            get_last_seen_id(
                temp_db,
                Provider.FINNHUB,
                Stream.MACRO,
                Scope.GLOBAL,
            )
            == 12345
        )

    def test_corrupted_id_row_returns_none(self, temp_db):
        with _cursor_context(temp_db) as cursor:
            cursor.execute(
                """
                INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    Provider.FINNHUB.value,
                    Stream.MACRO.value,
                    Scope.GLOBAL.value,
                    "__GLOBAL__",
                    None,
                    "not-an-int",
                ),
            )

        result = get_last_seen_id(
            temp_db,
            Provider.FINNHUB,
            Stream.MACRO,
            Scope.GLOBAL,
        )
        assert result is None
