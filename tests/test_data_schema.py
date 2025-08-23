"""
Database schema constraint tests.
Tests database-level CHECK constraints by bypassing Python validation.
Uses direct SQL operations to validate constraint enforcement.
"""

import sqlite3
import os
import sys
import tempfile
import gc
import pytest

# Add parent directory to path to import data module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add tests directory to path to import conftest
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.storage import init_database
from conftest import cleanup_sqlite_artifacts



def has_json1_support(db_path: str) -> bool:
    """Check if SQLite has JSON1 extension for conditional tests."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT json_valid('{}')")
            return True
    except sqlite3.OperationalError:
        return False


@pytest.fixture
def test_db():
    """Windows-safe temporary database with schema for constraint testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # Close file handle immediately for Windows
    
    try:
        init_database(db_path)
        yield db_path
    finally:
        cleanup_sqlite_artifacts(db_path)


class TestNotNullConstraints:
    """Test NOT NULL constraints across all tables."""
    
    def test_news_items_required_fields(self, test_db):
        """Test NOT NULL constraints on news_items table."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Test symbol NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO news_items (symbol, url, headline, published_iso, source)
                    VALUES (NULL, 'http://test.com', 'Test', '2024-01-01T10:00:00Z', 'test')
                """)
            
            # Test url NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO news_items (symbol, url, headline, published_iso, source)
                    VALUES ('AAPL', NULL, 'Test', '2024-01-01T10:00:00Z', 'test')
                """)
            
            # Test headline NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO news_items (symbol, url, headline, published_iso, source)
                    VALUES ('AAPL', 'http://test.com', NULL, '2024-01-01T10:00:00Z', 'test')
                """)
    
    def test_price_data_required_fields(self, test_db):
        """Test NOT NULL constraints on price_data table."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Test symbol NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES (NULL, '2024-01-01T10:00:00Z', '150.00')
                """)
            
            # Test timestamp_iso NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES ('AAPL', NULL, '150.00')
                """)
            
            # Test price NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES ('AAPL', '2024-01-01T10:00:00Z', NULL)
                """)
    
    def test_analysis_results_required_fields(self, test_db):
        """Test NOT NULL constraints on analysis_results table."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Test model_name NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('AAPL', 'news_analysis', NULL, 'BULL', 0.85, '2024-01-01T10:00:00Z', '{}')
                """)
            
            # Test result_json NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('AAPL', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', NULL)
                """)
    
    def test_holdings_required_fields(self, test_db):
        """Test NOT NULL constraints on holdings table."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Test quantity NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('AAPL', NULL, '150.00', '1500.00')
                """)
            
            # Test break_even_price NOT NULL
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('AAPL', '10', NULL, '1500.00')
                """)

class TestFinancialConstraints:
    """Test positive value constraints for financial fields."""
    
    def test_price_must_be_positive(self, test_db):
        """Test price > 0 constraint in price_data."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: small positive price
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price)
                VALUES ('AAPL', '2024-01-01T10:00:00Z', '0.000001')
            """)
            
            # Invalid: zero price
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES ('AAPL', '2024-01-01T11:00:00Z', '0')
                """)
            
            # Invalid: negative price
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES ('AAPL', '2024-01-01T12:00:00Z', '-1.50')
                """)
    
    def test_price_boundary_values(self, test_db):
        """Test price constraint with boundary values."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: very small positive
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price)
                VALUES ('TEST1', '2024-01-01T10:00:00Z', '0.000001')
            """)
            
            # Valid: very large positive
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price)
                VALUES ('TEST2', '2024-01-01T10:00:00Z', '999999999.99')
            """)
            
            # Invalid: non-numeric text casts to 0.0, which violates price > 0 constraint
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES ('TEST3', '2024-01-01T10:00:00Z', 'not_a_number')
                """)
    
    def test_holdings_quantity_positive(self, test_db):
        """Test quantity > 0 constraint in holdings."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: positive quantity
            cursor.execute("""
                INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                VALUES ('AAPL', '10.5', '150.00', '1575.00')
            """)
            
            # Invalid: zero quantity
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('TSLA', '0', '200.00', '0')
                """)
    
    def test_holdings_break_even_positive(self, test_db):
        """Test break_even_price > 0 constraint in holdings."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Invalid: zero break_even_price
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('MSFT', '5', '0', '1000.00')
                """)
            
            # Invalid: negative break_even_price
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('GOOGL', '5', '-100.00', '500.00')
                """)
    
    def test_holdings_total_cost_positive(self, test_db):
        """Test total_cost > 0 constraint in holdings."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Invalid: zero total_cost
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('NVDA', '10', '100.00', '0')
                """)
            
            # Invalid: negative total_cost
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('AMD', '10', '80.00', '-800.00')
                """)


class TestPrimaryKeyConstraints:
    """Test primary key uniqueness constraints."""
    
    def test_news_items_composite_key(self, test_db):
        """Test (symbol, url) composite primary key on news_items."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # First insert succeeds
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('AAPL', 'http://example.com/1', 'News 1', '2024-01-01T10:00:00Z', 'test')
            """)
            
            # Duplicate key fails
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                cursor.execute("""
                    INSERT INTO news_items (symbol, url, headline, published_iso, source)
                    VALUES ('AAPL', 'http://example.com/1', 'Different News', '2024-01-01T11:00:00Z', 'test2')
                """)
            
            # Different symbol with same URL succeeds
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('TSLA', 'http://example.com/1', 'Tesla News', '2024-01-01T10:00:00Z', 'test')
            """)
    
    def test_price_data_composite_key(self, test_db):
        """Test (symbol, timestamp_iso) composite primary key on price_data."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # First insert succeeds
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price)
                VALUES ('AAPL', '2024-01-01T10:00:00Z', '150.00')
            """)
            
            # Duplicate key fails
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price)
                    VALUES ('AAPL', '2024-01-01T10:00:00Z', '151.00')
                """)
            
            # Different timestamp with same symbol succeeds
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price)
                VALUES ('AAPL', '2024-01-01T11:00:00Z', '151.00')
            """)
    
    def test_analysis_results_composite_key(self, test_db):
        """Test (symbol, analysis_type) composite primary key on analysis_results."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # First insert succeeds
            cursor.execute("""
                INSERT INTO analysis_results 
                (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                VALUES ('AAPL', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', '{}')
            """)
            
            # Duplicate key fails
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('AAPL', 'news_analysis', 'claude', 'BEAR', 0.60, '2024-01-01T11:00:00Z', '{}')
                """)
    
    def test_holdings_single_key(self, test_db):
        """Test symbol primary key on holdings."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # First insert succeeds
            cursor.execute("""
                INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                VALUES ('AAPL', '10', '150.00', '1500.00')
            """)
            
            # Duplicate symbol fails
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                cursor.execute("""
                    INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                    VALUES ('AAPL', '20', '155.00', '3100.00')
                """)


class TestVolumeConstraints:
    """Test volume >= 0 constraint with NULL handling."""
    
    def test_volume_non_negative(self, test_db):
        """Test volume >= 0 constraint in price_data."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: zero volume
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, volume)
                VALUES ('AAPL', '2024-01-01T10:00:00Z', '150.00', 0)
            """)
            
            # Valid: positive volume
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, volume)
                VALUES ('AAPL', '2024-01-01T11:00:00Z', '150.00', 1000000)
            """)
            
            # Invalid: negative volume
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price, volume)
                    VALUES ('AAPL', '2024-01-01T12:00:00Z', '150.00', -1)
                """)
    
    def test_volume_null_allowed(self, test_db):
        """Test that NULL volume is allowed."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: NULL volume (should pass CHECK constraint)
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, volume)
                VALUES ('AAPL', '2024-01-01T13:00:00Z', '150.00', NULL)
            """)
            
            # Verify it was inserted with NULL
            result = cursor.execute("""
                SELECT volume FROM price_data 
                WHERE symbol='AAPL' AND timestamp_iso='2024-01-01T13:00:00Z'
            """).fetchone()
            assert result[0] is None


class TestEnumConstraints:
    """Test enum value constraints."""
    
    def test_session_enum_values(self, test_db):
        """Test session IN ('REG', 'PRE', 'POST') constraint."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid values (using realistic US market hours in UTC)
            # Assuming EDT (UTC-4): PRE: 8-13:30 UTC, REG: 13:30-20 UTC, POST: 20-24 UTC
            session_hours = {'REG': '14', 'PRE': '09', 'POST': '21'}
            for session in ['REG', 'PRE', 'POST']:
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price, session)
                    VALUES (?, ?, '150.00', ?)
                """, (f'TEST_{session}', f'2024-01-01T{session_hours[session]}:00:00Z', session))
            
            # Invalid: wrong case
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price, session)
                    VALUES ('TEST', '2024-01-01T14:00:00Z', '150.00', 'reg')
                """)
            
            # Invalid: not in enum
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price, session)
                    VALUES ('TEST', '2024-01-01T15:00:00Z', '150.00', 'EXTENDED')
                """)
    
    def test_stance_enum_values(self, test_db):
        """Test stance IN ('BULL', 'BEAR', 'NEUTRAL') constraint."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid values
            for stance in ['BULL', 'BEAR', 'NEUTRAL']:
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES (?, 'news_analysis', 'gpt-4', ?, 0.75, '2024-01-01T10:00:00Z', '{}')
                """, (f'TEST_{stance}', stance))
            
            # Invalid: lowercase
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('TEST', 'sentiment_analysis', 'gpt-4', 'bull', 0.75, '2024-01-01T10:00:00Z', '{}')
                """)
    
    def test_analysis_type_enum_values(self, test_db):
        """Test analysis_type enum constraint."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid values
            valid_types = ['news_analysis', 'sentiment_analysis', 'sec_filings', 'head_trader']
            for i, atype in enumerate(valid_types):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES (?, ?, 'gpt-4', 'BULL', 0.75, '2024-01-01T10:00:00Z', '{}')
                """, (f'TEST{i}', atype))
            
            # Invalid: uppercase
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('INVALID', 'NEWS_ANALYSIS', 'gpt-4', 'BULL', 0.75, '2024-01-01T10:00:00Z', '{}')
                """)


class TestConfidenceScoreRange:
    """Test confidence score BETWEEN 0 AND 1 constraint."""
    
    def test_confidence_score_boundaries(self, test_db):
        """Test confidence_score boundary values."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: exactly 0.0
            cursor.execute("""
                INSERT INTO analysis_results 
                (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                VALUES ('TEST1', 'news_analysis', 'gpt-4', 'NEUTRAL', 0.0, '2024-01-01T10:00:00Z', '{}')
            """)
            
            # Valid: exactly 1.0
            cursor.execute("""
                INSERT INTO analysis_results 
                (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                VALUES ('TEST2', 'news_analysis', 'gpt-4', 'BULL', 1.0, '2024-01-01T10:00:00Z', '{}')
            """)
            
            # Valid: mid-range
            cursor.execute("""
                INSERT INTO analysis_results 
                (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                VALUES ('TEST3', 'news_analysis', 'gpt-4', 'BEAR', 0.5, '2024-01-01T10:00:00Z', '{}')
            """)
    
    def test_confidence_score_out_of_range(self, test_db):
        """Test confidence_score values outside 0-1 range."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Invalid: below 0
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('TEST', 'sentiment_analysis', 'gpt-4', 'BULL', -0.1, '2024-01-01T10:00:00Z', '{}')
                """)
            
            # Invalid: above 1
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('TEST', 'sec_filings', 'gpt-4', 'BEAR', 1.1, '2024-01-01T10:00:00Z', '{}')
                """)


class TestJSONConstraints:
    """Test JSON validation constraints (conditional on JSON1 extension)."""
    
    def test_json_valid_constraint(self, test_db):
        """Test json_valid() constraint."""
        if not has_json1_support(test_db):
            pytest.skip("SQLite JSON1 extension not available")
        
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: proper JSON object
            cursor.execute("""
                INSERT INTO analysis_results 
                (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                VALUES ('TEST1', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', '{"key": "value"}')
            """)
            
            # Invalid: malformed JSON
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('TEST2', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', '{invalid json')
                """)
    
    def test_json_type_object_constraint(self, test_db):
        """Test json_type() = 'object' constraint."""
        if not has_json1_support(test_db):
            pytest.skip("SQLite JSON1 extension not available")
        
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Valid: JSON object
            cursor.execute("""
                INSERT INTO analysis_results 
                (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                VALUES ('TEST3', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', '{}')
            """)
            
            # Invalid: JSON array
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('TEST4', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', '[]')
                """)
            
            # Invalid: JSON primitive
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json)
                    VALUES ('TEST5', 'news_analysis', 'gpt-4', 'BULL', 0.85, '2024-01-01T10:00:00Z', '"string"')
                """)


class TestDefaultValues:
    """Test default value behavior."""
    
    def test_session_default_reg(self, test_db):
        """Test session defaults to 'REG' when not specified."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
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
            assert result[0] == 'REG'
    
    def test_timestamp_defaults(self, test_db):
        """Test created_at_iso defaults to current timestamp."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Insert without specifying created_at_iso
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('AAPL', 'http://example.com/test', 'Test News', '2024-01-01T10:00:00Z', 'test')
            """)
            
            # Verify timestamp was set
            result = cursor.execute("""
                SELECT created_at_iso FROM news_items 
                WHERE symbol='AAPL' AND url='http://example.com/test'
            """).fetchone()
            
            # Should be an ISO timestamp
            assert result[0] is not None
            assert 'T' in result[0]  # ISO format check
            assert result[0].endswith('Z')  # UTC timezone marker


class TestTableStructure:
    """Test table structure and optimizations."""
    
    def test_without_rowid_optimization(self, test_db):
        """Test that all tables use WITHOUT ROWID optimization."""
        with sqlite3.connect(test_db) as conn:
            cursor = conn.cursor()
            
            # Get all table creation SQL
            tables = cursor.execute("""
                SELECT name, sql FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """).fetchall()
            
            # Verify each table has WITHOUT ROWID
            for name, sql in tables:
                assert 'WITHOUT ROWID' in sql.upper(), f"Table {name} missing WITHOUT ROWID"
            
            # Should have exactly 4 tables
            assert len(tables) == 4
            table_names = [name for name, _ in tables]
            assert 'news_items' in table_names
            assert 'price_data' in table_names
            assert 'analysis_results' in table_names
            assert 'holdings' in table_names


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])