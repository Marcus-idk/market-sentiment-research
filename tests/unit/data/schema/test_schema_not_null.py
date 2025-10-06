"""
Tests NOT NULL constraints for required database fields.
"""

import sqlite3
import pytest

from data.storage import init_database
from data.storage.db_context import _cursor_context

class TestNotNullConstraints:
    """Test NOT NULL constraints across all tables."""
    
    def test_news_items_required_fields(self, temp_db):
        """Test NOT NULL constraints on news_items table."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_news_labels_required_fields(self, temp_db):
        """Test NOT NULL constraints on news_labels table."""
        with _cursor_context(temp_db) as cursor:

            # Prepare backing news rows for FK
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('AAPL', 'http://example.com/labels-symbol', 'Label Test', '2024-01-01T10:00:00Z', 'test')
            """)
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('AAPL', 'http://example.com/labels-url', 'Label Test', '2024-01-01T10:05:00Z', 'test')
            """)
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('AAPL', 'http://example.com/labels-type', 'Label Test', '2024-01-01T10:10:00Z', 'test')
            """)

            with pytest.raises(sqlite3.IntegrityError, match='NOT NULL'):
                cursor.execute("""
                    INSERT INTO news_labels (symbol, url, label)
                    VALUES (NULL, 'http://example.com/labels-symbol', 'Company')
                """)

            with pytest.raises(sqlite3.IntegrityError, match='NOT NULL'):
                cursor.execute("""
                    INSERT INTO news_labels (symbol, url, label)
                    VALUES ('AAPL', NULL, 'Company')
                """)

            with pytest.raises(sqlite3.IntegrityError, match='NOT NULL'):
                cursor.execute("""
                    INSERT INTO news_labels (symbol, url, label)
                    VALUES ('AAPL', 'http://example.com/labels-type', NULL)
                """)

    def test_price_data_required_fields(self, temp_db):
        """Test NOT NULL constraints on price_data table."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_analysis_results_required_fields(self, temp_db):
        """Test NOT NULL constraints on analysis_results table."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_holdings_required_fields(self, temp_db):
        """Test NOT NULL constraints on holdings table."""
        with _cursor_context(temp_db) as cursor:
            
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
