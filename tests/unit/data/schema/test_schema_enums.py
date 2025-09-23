"""
Tests enum value constraints and locks critical enum values against changes.
"""

import sqlite3
import pytest

from data.storage import init_database, _cursor_context
from data.models import Session, Stance, AnalysisType, NewsLabelType


class TestEnumValueLocks:
    """Test that enum values never change (would break database)."""
    
    def test_session_enum_values_unchanged(self):
        """Lock Session enum values - these are stored in database."""
        # These exact string values are persisted in the database
        # Changing them would break all existing records
        assert Session.REG.value == "REG"
        assert Session.PRE.value == "PRE"
        assert Session.POST.value == "POST"
        assert Session.CLOSED.value == "CLOSED"
        
        # Verify enum has exactly these 4 values
        assert len(Session) == 4
        assert set(s.value for s in Session) == {"REG", "PRE", "POST", "CLOSED"}
    
    def test_stance_enum_values_unchanged(self):
        """Lock Stance enum values - these are stored in database."""
        # These exact string values are persisted in the database
        # Changing them would break all existing records
        assert Stance.BULL.value == "BULL"
        assert Stance.BEAR.value == "BEAR"
        assert Stance.NEUTRAL.value == "NEUTRAL"
        
        # Verify enum has exactly these 3 values
        assert len(Stance) == 3
        assert set(s.value for s in Stance) == {"BULL", "BEAR", "NEUTRAL"}
    
    def test_analysis_type_enum_values_unchanged(self):
        """Lock AnalysisType enum values - these are stored in database."""
        # These exact string values are persisted in the database
        # Changing them would break all existing records
        assert AnalysisType.NEWS_ANALYSIS.value == "news_analysis"
        assert AnalysisType.SENTIMENT_ANALYSIS.value == "sentiment_analysis"
        assert AnalysisType.SEC_FILINGS.value == "sec_filings"
        assert AnalysisType.HEAD_TRADER.value == "head_trader"
        
        # Verify enum has exactly these 4 values
        assert len(AnalysisType) == 4
        assert set(a.value for a in AnalysisType) == {
            "news_analysis", "sentiment_analysis", "sec_filings", "head_trader"
        }

    def test_news_label_enum_values_unchanged(self):
        """Lock NewsLabelType values - stored in database for labels."""
        assert NewsLabelType.COMPANY.value == 'Company'
        assert NewsLabelType.PEOPLE.value == 'People'
        assert NewsLabelType.MARKET_WITH_MENTION.value == 'MarketWithMention'
        assert len(NewsLabelType) == 3
        assert set(label.value for label in NewsLabelType) == {'Company', 'People', 'MarketWithMention'}


class TestEnumConstraints:
    """Test enum value constraints."""
    
    def test_session_enum_values(self, temp_db):
        """Test session IN ('REG', 'PRE', 'POST', 'CLOSED') constraint."""
        with _cursor_context(temp_db) as cursor:
            
            # Valid enum values - test data with different hours for each session type
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
        with _cursor_context(temp_db) as cursor:
            
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
        with _cursor_context(temp_db) as cursor:
            
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

    def test_news_label_enum_values(self, temp_db):
        """Test news_labels label constraint values."""
        with _cursor_context(temp_db) as cursor:

            for suffix, label in enumerate(['Company', 'People', 'MarketWithMention']):
                cursor.execute("""
                    INSERT INTO news_items (symbol, url, headline, published_iso, source)
                    VALUES ('AAPL', 'http://example.com/enum-' || ?, 'Enum Value', '2024-01-01T10:00:00Z', 'test')
                """, (suffix,))
                cursor.execute("""
                    INSERT INTO news_labels (symbol, url, label)
                    VALUES ('AAPL', 'http://example.com/enum-' || ?, ?)
                """, (suffix, label))

            with pytest.raises(sqlite3.IntegrityError, match='CHECK constraint failed'):
                cursor.execute("""
                    INSERT INTO news_labels (symbol, url, label)
                    VALUES ('AAPL', 'http://example.com/enum-invalid', 'InvalidLabel')
                """)

