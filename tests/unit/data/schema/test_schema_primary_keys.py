"""
Tests primary key uniqueness constraints for all database tables.
"""

import sqlite3
import pytest

from data.storage import init_database
from data.storage.db_context import _cursor_context

class TestPrimaryKeyConstraints:
    """Test primary key uniqueness constraints."""
    
    def test_news_items_composite_key(self, temp_db):
        """Test (symbol, url) composite primary key on news_items."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_news_labels_composite_key(self, temp_db):
        """Test (symbol, url) composite primary key on news_labels."""
        with _cursor_context(temp_db) as cursor:

            # Backing news rows required for foreign key reference
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('AAPL', 'http://example.com/label', 'Label News', '2024-01-01T10:00:00Z', 'test')
            """)
            cursor.execute("""
                INSERT INTO news_items (symbol, url, headline, published_iso, source)
                VALUES ('TSLA', 'http://example.com/label', 'TSLA Label News', '2024-01-01T10:05:00Z', 'test')
            """)

            # First label succeeds
            cursor.execute("""
                INSERT INTO news_labels (symbol, url, label)
                VALUES ('AAPL', 'http://example.com/label', 'Company')
            """)

            # Duplicate key fails
            with pytest.raises(sqlite3.IntegrityError, match='UNIQUE constraint failed'):
                cursor.execute("""
                    INSERT INTO news_labels (symbol, url, label)
                    VALUES ('AAPL', 'http://example.com/label', 'People')
                """)

            # Different symbol with same URL succeeds
            cursor.execute("""
                INSERT INTO news_labels (symbol, url, label)
                VALUES ('TSLA', 'http://example.com/label', 'People')
            """)

    def test_price_data_composite_key(self, temp_db):
        """Test (symbol, timestamp_iso) composite primary key on price_data."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_analysis_results_composite_key(self, temp_db):
        """Test (symbol, analysis_type) composite primary key on analysis_results."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_holdings_single_key(self, temp_db):
        """Test symbol primary key on holdings."""
        with _cursor_context(temp_db) as cursor:
            
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
