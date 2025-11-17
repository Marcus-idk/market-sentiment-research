"""Schema checks for the last_seen_state watermark table."""

import sqlite3

import pytest

from data.storage.db_context import _cursor_context


class TestLastSeenStateSchema:
    """Validate column layout and constraints for last_seen_state."""

    def test_table_has_expected_columns(self, temp_db):
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA table_info(last_seen_state)")
            columns = [row["name"] for row in cursor.fetchall()]

        assert columns == [
            "provider",
            "stream",
            "scope",
            "symbol",
            "timestamp",
            "id",
        ]

    def test_primary_key_enforces_uniqueness(self, temp_db):
        with _cursor_context(temp_db) as cursor:
            cursor.execute(
                """
                INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
                VALUES ('FINNHUB', 'MACRO', 'GLOBAL', '__GLOBAL__', NULL, 1)
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            with _cursor_context(temp_db) as cursor:
                cursor.execute(
                    """
                    INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
                    VALUES ('FINNHUB', 'MACRO', 'GLOBAL', '__GLOBAL__', NULL, 2)
                    """
                )

    def test_scope_check_constraint(self, temp_db):
        with pytest.raises(sqlite3.IntegrityError):
            with _cursor_context(temp_db) as cursor:
                cursor.execute(
                    """
                    INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
                    VALUES ('FINNHUB', 'MACRO', 'INVALID', '__GLOBAL__', NULL, NULL)
                    """
                )
