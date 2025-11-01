"""Tests database table structure, default values, and schema creation."""

from data.storage.db_context import _cursor_context


class TestDefaultValues:
    """Test default value behavior."""

    def test_session_default_reg(self, temp_db):
        """Test session defaults to 'REG' when not specified."""
        with _cursor_context(temp_db) as cursor:
            # Insert without specifying session
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price)
                VALUES ('AAPL', '2024-01-01T10:00:00Z', '150.00')
            """)

            # Verify default value
            result = cursor.execute("""
                SELECT session FROM price_data 
                WHERE symbol='AAPL' AND timestamp_iso='2024-01-01T10:00:00Z'
            """).fetchone()
            assert result[0] == "REG"

    def test_timestamp_defaults(self, temp_db):
        """Test created_at_iso defaults to current timestamp."""
        with _cursor_context(temp_db) as cursor:
            # Insert without specifying created_at_iso
            cursor.execute(
                """
                INSERT INTO news_items (url, headline, published_iso, source, news_type)
                VALUES (
                    'http://example.com/test',
                    'Test News',
                    '2024-01-01T10:00:00Z',
                    'test',
                    'macro'
                )
                """
            )

            # Verify timestamp was set
            result = cursor.execute("""
                SELECT created_at_iso FROM news_items 
                WHERE url='http://example.com/test'
            """).fetchone()

            # Should be an ISO timestamp
            assert result[0] is not None
            assert "T" in result[0]  # ISO format check
            assert result[0].endswith("Z")  # UTC timezone marker

    def test_news_symbols_timestamp_default(self, temp_db):
        """Test created_at_iso default for news_symbols table."""
        with _cursor_context(temp_db) as cursor:
            cursor.execute(
                """
                INSERT INTO news_items (url, headline, published_iso, source, news_type)
                VALUES (
                    'http://example.com/label-default',
                    'Label Default',
                    '2024-01-01T10:00:00Z',
                    'test',
                    'macro'
                )
                """
            )
            cursor.execute("""
                INSERT INTO news_symbols (url, symbol, is_important)
                VALUES ('http://example.com/label-default', 'AAPL', 1)
            """)

            result = cursor.execute("""
                SELECT created_at_iso FROM news_symbols
                WHERE url='http://example.com/label-default' AND symbol='AAPL'
            """).fetchone()

            assert result[0] is not None
            assert "T" in result[0]
            assert result[0].endswith("Z")


class TestTableStructure:
    """Test table structure and optimizations."""

    def test_without_rowid_optimization(self, temp_db):
        """All user tables use WITHOUT ROWID and required tables exist."""
        with _cursor_context(temp_db) as cursor:
            # Get all non-internal table creation SQL
            tables = cursor.execute(
                """
                SELECT name, sql FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()

            # Required tables (update here when schema grows)
            required = {
                "news_items",
                "news_symbols",
                "price_data",
                "analysis_results",
                "holdings",
                "last_seen",
            }

            names = {name for name, _ in tables}
            missing = required - names
            assert not missing

            # Verify each table uses WITHOUT ROWID
            for _name, sql in tables:
                assert "WITHOUT ROWID" in sql.upper()
