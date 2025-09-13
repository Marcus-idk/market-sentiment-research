"""
Database schema constraint tests.
Tests database-level CHECK constraints by bypassing Python validation.
Uses direct SQL operations to validate constraint enforcement.
"""

import sqlite3
import gc
import pytest

from data.storage import init_database

class TestEnumConstraints:
    """Test enum value constraints."""
    
    def test_session_enum_values(self, temp_db):
        """Test session IN ('REG', 'PRE', 'POST', 'CLOSED') constraint."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            
            # Valid values (using realistic US market hours in UTC)
            # Assuming EDT (UTC-4): PRE: 08:00–13:30 UTC, REG: 13:30–20:00 UTC, POST: 20:00–24:00 UTC, CLOSED: 00:00–08:00 UTC
            session_hours = {'REG': '14', 'PRE': '09', 'POST': '21', 'CLOSED': '02'}
            for session in ['REG', 'PRE', 'POST', 'CLOSED']:
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
    
    def test_stance_enum_values(self, temp_db):
        """Test stance IN ('BULL', 'BEAR', 'NEUTRAL') constraint."""
        with sqlite3.connect(temp_db) as conn:
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
    
    def test_analysis_type_enum_values(self, temp_db):
        """Test analysis_type enum constraint."""
        with sqlite3.connect(temp_db) as conn:
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
