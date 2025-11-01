"""
Tests database initialization and schema creation.
"""

import pytest

from data.storage import init_database
from data.storage.db_context import _cursor_context


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

            required_tables = {"analysis_results", "holdings", "news_items", "price_data"}
            assert required_tables.issubset(tables)

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
        monkeypatch.setattr("data.storage.storage_core.files", mock_files)

        with pytest.raises(FileNotFoundError, match="schema.sql"):
            init_database(temp_db_path)

    def test_wal_mode_enabled(self, temp_db):
        """Test WAL mode is properly enabled (requires file-backed DB)"""
        # Check WAL mode is enabled (database already initialized by fixture)
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

    def test_foreign_keys_enabled_by_default(self, temp_db):
        """Canary: every test connection should enforce FK constraints."""
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA foreign_keys")
            val = cursor.fetchone()[0]
            assert val == 1
