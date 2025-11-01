"""
Tests last_seen timestamp tracking for data providers.
"""

import sqlite3
from datetime import UTC, datetime

import pytest

from data.storage import (
    get_last_macro_min_id,
    get_last_news_time,
    get_last_seen,
    set_last_macro_min_id,
    set_last_news_time,
    set_last_seen,
)
from data.storage.db_context import _cursor_context


class TestLastSeenState:
    """Test last_seen table key-value storage operations"""

    def test_basic_roundtrip_set_get(self, temp_db):
        """Test basic set/get functionality"""
        # Set a key-value pair using allowed key
        set_last_seen(temp_db, "news_since_iso", "2024-01-15T10:30:00Z")

        # Retrieve it
        result = get_last_seen(temp_db, "news_since_iso")
        assert result == "2024-01-15T10:30:00Z"

    def test_replace_existing_key(self, temp_db):
        """Test INSERT OR REPLACE behavior - overwriting existing keys"""
        # Set initial value
        set_last_seen(temp_db, "llm_last_run_iso", "2024-01-15T09:00:00Z")
        assert get_last_seen(temp_db, "llm_last_run_iso") == "2024-01-15T09:00:00Z"

        # Overwrite with new value
        set_last_seen(temp_db, "llm_last_run_iso", "2024-01-15T10:00:00Z")

        # Should return the new value only
        result = get_last_seen(temp_db, "llm_last_run_iso")
        assert result == "2024-01-15T10:00:00Z"

        # Verify only one record exists
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM last_seen WHERE key = 'llm_last_run_iso'")
            count = cursor.fetchone()[0]
            assert count == 1

    def test_unknown_key_returns_none(self, temp_db):
        """Test that non-existent keys return None"""
        # Test with allowed key that hasn't been set
        result = get_last_seen(temp_db, "news_since_iso")
        assert result is None

    def test_unicode_safety(self, temp_db):
        """Test unicode handling in values and key constraint enforcement"""
        # Test unicode value with allowed key
        unicode_value = "résumé📈"
        set_last_seen(temp_db, "news_since_iso", unicode_value)
        result = get_last_seen(temp_db, "news_since_iso")
        assert result == unicode_value

        # Test both allowed keys work
        set_last_seen(temp_db, "llm_last_run_iso", "2024-01-15T10:30:00Z")
        result = get_last_seen(temp_db, "llm_last_run_iso")
        assert result == "2024-01-15T10:30:00Z"

    def test_key_constraint_enforcement(self, temp_db):
        """Test that CHECK constraint rejects invalid keys"""
        # Should raise constraint error for invalid key
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            set_last_seen(temp_db, "invalid_key", "some_value")


class TestLastNewsTime:
    """Test specialized last news time tracking functions"""

    def test_roundtrip_aware_timestamp(self, temp_db):
        """Test UTC-aware datetime roundtrip"""
        # Set a UTC-aware timestamp
        dt_aware = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        set_last_news_time(temp_db, dt_aware)

        # Retrieve it
        result = get_last_news_time(temp_db)

        # Should be equal when both are UTC-aware
        assert result == dt_aware
        assert result.tzinfo == UTC

        # Check underlying storage format
        raw_value = get_last_seen(temp_db, "news_since_iso")
        assert raw_value == "2024-01-15T10:30:45Z"

    def test_naive_timestamp_treated_as_utc(self, temp_db):
        """Test naive datetime is treated as UTC"""
        # Set naive timestamp
        dt_naive = datetime(2024, 1, 15, 10, 30, 45)
        set_last_news_time(temp_db, dt_naive)

        # Retrieve it - should be UTC-aware
        result = get_last_news_time(temp_db)
        expected = dt_naive.replace(tzinfo=UTC)

        assert result == expected
        assert result.tzinfo == UTC

        # Check underlying storage format
        raw_value = get_last_seen(temp_db, "news_since_iso")
        assert raw_value == "2024-01-15T10:30:45Z"

    def test_overwrite_behavior(self, temp_db):
        """Test last write wins - no monotonic enforcement"""
        # Set older time first
        older_time = datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
        set_last_news_time(temp_db, older_time)
        assert get_last_news_time(temp_db) == older_time

        # Set newer time
        newer_time = datetime(2024, 1, 15, 11, 0, tzinfo=UTC)
        set_last_news_time(temp_db, newer_time)
        assert get_last_news_time(temp_db) == newer_time

        # Set even older time - should still work (last write wins)
        much_older_time = datetime(2024, 1, 14, 8, 0, tzinfo=UTC)
        set_last_news_time(temp_db, much_older_time)
        assert get_last_news_time(temp_db) == much_older_time

    def test_missing_key_returns_none(self, temp_db):
        """Test None returned when news_since_iso key doesn't exist"""
        # Don't set anything
        result = get_last_news_time(temp_db)
        assert result is None


class TestLastMacroMinId:
    """Test specialized macro news min_id tracking functions"""

    def test_macro_min_id_roundtrip_int(self, temp_db):
        """Test basic get/set flow for integer watermark"""
        # Set integer watermark
        set_last_macro_min_id(temp_db, 12345)

        # Retrieve it
        result = get_last_macro_min_id(temp_db)

        # Should be equal as integer
        assert result == 12345
        assert isinstance(result, int)

        # Check underlying storage (stored as string)
        raw_value = get_last_seen(temp_db, "macro_news_min_id")
        assert raw_value == "12345"

    def test_macro_min_id_missing_returns_none(self, temp_db):
        """Test first-run behavior when no watermark exists"""
        # Fresh database - never called set_last_macro_min_id
        result = get_last_macro_min_id(temp_db)

        # Should return None to indicate bootstrap needed
        assert result is None

    def test_macro_min_id_overwrite_and_nonint_value_returns_none(self, temp_db):
        """Test overwrite behavior and graceful failure on corrupted data"""
        # Test overwrite: last write wins
        set_last_macro_min_id(temp_db, 100)
        assert get_last_macro_min_id(temp_db) == 100

        set_last_macro_min_id(temp_db, 200)
        assert get_last_macro_min_id(temp_db) == 200

        # Test corrupted data: manually set non-int value
        set_last_seen(temp_db, "macro_news_min_id", "garbage")

        # Should return None without crashing
        result = get_last_macro_min_id(temp_db)
        assert result is None
