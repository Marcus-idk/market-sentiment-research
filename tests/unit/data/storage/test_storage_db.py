"""
Tests database initialization and schema creation.
"""

import pytest
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from data.storage import (
    init_database, store_news_items, store_price_data,
    get_news_since, get_price_data_since, upsert_analysis_result,
    upsert_holdings, get_all_holdings, get_analysis_results,
    get_last_seen, set_last_seen, get_last_news_time, set_last_news_time,
    get_news_before, get_prices_before, commit_llm_batch, finalize_database,
)
from data.storage.db_context import _cursor_context
from data.storage.storage_utils import _normalize_url, _datetime_to_iso, _decimal_to_text, _iso_to_datetime

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)

class TestDatabaseInitialization:
    """Test database initialization and schema setup"""
    
    def test_init_database_creates_schema(self, temp_db_path):
        """Test database initialization creates all required tables"""
        # Initialize database
        init_database(temp_db_path)
        
        # Verify all 4 tables were created
        with _cursor_context(temp_db_path, commit=False) as cursor:
            # Check table existence
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)
            tables = {row[0] for row in cursor.fetchall()}

            required_tables = {'analysis_results', 'holdings', 'news_items', 'price_data'}
            assert required_tables.issubset(tables), f"Required tables {required_tables} not found. Got: {tables}"
    
    def test_schema_file_not_found_raises_error(self, temp_db_path, monkeypatch):
        """Test error when schema.sql resource is missing"""
        # Mock the files function directly in the storage module
        def mock_files(package):
            class MockPath:
                def joinpath(self, name):
                    return self
                def read_text(self):
                    raise FileNotFoundError("Resource 'schema.sql' not found in package 'data'")
            return MockPath()
        
        # Patch the files function in the storage_core module
        monkeypatch.setattr('data.storage.storage_core.files', mock_files)
        
        with pytest.raises(FileNotFoundError, match="schema.sql"):
            init_database(temp_db_path)
    
    def test_wal_mode_enabled(self, temp_db):
        """Test WAL mode is properly enabled (requires file-backed DB)"""
        # Check WAL mode is enabled (database already initialized by fixture)
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == 'wal', f"Expected WAL mode, got {mode}"

    def test_foreign_keys_enabled_by_default(self, temp_db):
        """Canary: every test connection should enforce FK constraints."""
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA foreign_keys")
            val = cursor.fetchone()[0]
            assert val == 1
