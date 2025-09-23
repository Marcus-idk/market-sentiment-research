"""
Tests financial value constraints for prices and decimal storage.
"""

import sqlite3
import pytest

from data.storage import init_database, _cursor_context

class TestFinancialConstraints:
    """Test positive value constraints for financial fields."""
    
    def test_price_must_be_positive(self, temp_db):
        """Test price > 0 constraint in price_data."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_price_boundary_values(self, temp_db):
        """Test price constraint with boundary values."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_holdings_quantity_positive(self, temp_db):
        """Test quantity > 0 constraint in holdings."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_holdings_break_even_positive(self, temp_db):
        """Test break_even_price > 0 constraint in holdings."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_holdings_total_cost_positive(self, temp_db):
        """Test total_cost > 0 constraint in holdings."""
        with _cursor_context(temp_db) as cursor:
            
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

class TestVolumeConstraints:
    """Test volume >= 0 constraint with NULL handling."""
    
    def test_volume_non_negative(self, temp_db):
        """Test volume >= 0 constraint in price_data."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_volume_null_allowed(self, temp_db):
        """Test that NULL volume is allowed."""
        with _cursor_context(temp_db) as cursor:
            
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
