"""
Tests confidence score range and JSON validation constraints.
"""

import sqlite3
import pytest

from data.storage import init_database
from data.storage.db_context import _cursor_context

def has_json1_support(db_path: str) -> bool:
    """Check if SQLite has JSON1 extension for conditional tests."""
    try:
        with _cursor_context(db_path, commit=False) as cursor:
            cursor.execute("SELECT json_valid('{}')")
            return True
    except sqlite3.OperationalError:
        return False

class TestConfidenceScoreRange:
    """Test confidence score BETWEEN 0 AND 1 constraint."""
    
    def test_confidence_score_boundaries(self, temp_db):
        """Test confidence_score boundary values."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_confidence_score_out_of_range(self, temp_db):
        """Test confidence_score values outside 0-1 range."""
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_json_valid_constraint(self, temp_db):
        """Test json_valid() constraint."""
        if not has_json1_support(temp_db):
            pytest.skip("SQLite JSON1 extension not available")
        
        with _cursor_context(temp_db) as cursor:
            
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
    
    def test_json_type_object_constraint(self, temp_db):
        """Test json_type() = 'object' constraint."""
        if not has_json1_support(temp_db):
            pytest.skip("SQLite JSON1 extension not available")
        
        with _cursor_context(temp_db) as cursor:
            
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
