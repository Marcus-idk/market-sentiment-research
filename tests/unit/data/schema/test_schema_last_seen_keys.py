"""Tests last_seen key CHECK constraint allows only specific watermark keys."""

import sqlite3

import pytest

from data.storage import set_last_seen


class TestLastSeenKeyConstraint:
    """Test CHECK constraint on last_seen.key column"""

    def test_last_seen_key_accepts_macro_news_min_id(self, temp_db):
        """Test CHECK constraint enforcement for allowed and invalid keys"""
        # Valid key: macro_news_min_id (should succeed)
        set_last_seen(temp_db, "macro_news_min_id", "123")

        # Valid key: news_since_iso (should succeed)
        set_last_seen(temp_db, "news_since_iso", "2024-01-15T10:00:00Z")

        # Valid key: llm_last_run_iso (should succeed)
        set_last_seen(temp_db, "llm_last_run_iso", "2024-01-15T10:00:00Z")

        # Invalid key: should raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            set_last_seen(temp_db, "random_key", "123")

        # Invalid key: typo protection
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            set_last_seen(temp_db, "news_since_iso_typo", "2024-01-15T10:00:00Z")
