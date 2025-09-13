"""
Tests analysis result storage operations and conflict resolution.
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
    _normalize_url, _datetime_to_iso, _decimal_to_text,
    get_last_seen, set_last_seen, get_last_news_time, set_last_news_time,
    get_news_before, get_prices_before, commit_llm_batch, finalize_database
)

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)

class TestAnalysisResultUpsert:
    """Test analysis result upsert operations"""
    
    def test_upsert_analysis_conflict_resolution(self, temp_db):
        """Test ON CONFLICT DO UPDATE for analysis results"""
        # Initial analysis result
        result1 = AnalysisResult(
            symbol="AAPL",
            analysis_type=AnalysisType.NEWS_ANALYSIS,
            model_name="gpt-4",
            stance=Stance.BULL,
            confidence_score=0.85,
            last_updated=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            result_json='{"sentiment": "positive"}',
            created_at=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        # Store initial result
        upsert_analysis_result(temp_db, result1)
        
        # Updated analysis result (same symbol+analysis_type = conflict)
        result2 = AnalysisResult(
            symbol="AAPL",
            analysis_type=AnalysisType.NEWS_ANALYSIS,  # Same primary key
            model_name="gpt-4o",  # Should update
            stance=Stance.NEUTRAL,  # Should update
            confidence_score=0.75,  # Should update
            last_updated=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),  # Should update
            result_json='{"sentiment": "neutral"}',  # Should update
            created_at=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)  # Should be ignored (preserve original)
        )
        
        # Upsert updated result
        upsert_analysis_result(temp_db, result2)
        
        # Verify record was updated, not duplicated
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*), model_name, stance, confidence_score, 
                       last_updated_iso, result_json, created_at_iso
                FROM analysis_results 
                WHERE symbol = 'AAPL' AND analysis_type = 'news_analysis'
            """)
            count, model, stance, confidence, updated, json_result, created = cursor.fetchone()
            
            assert count == 1, f"Expected 1 record, got {count}"
            assert model == "gpt-4o", "model_name should be updated"
            assert stance == "NEUTRAL", "stance should be updated"
            assert confidence == 0.75, "confidence should be updated"
            assert updated == "2024-01-15T11:00:00Z", "last_updated should be updated"
            assert json_result == '{"sentiment": "neutral"}', "result_json should be updated"
            assert created == "2024-01-15T09:00:00Z", "created_at should be preserved from first insert"
    
    def test_upsert_analysis_auto_created_at(self, temp_db):
        """Test automatic created_at when not provided"""
        # Analysis result without created_at
        result = AnalysisResult(
            symbol="TSLA",
            analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
            model_name="claude-3",
            stance=Stance.BEAR,
            confidence_score=0.90,
            last_updated=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            result_json='{"sentiment": "bearish"}'
            # created_at not provided
        )
        
        # Store result
        upsert_analysis_result(temp_db, result)
        
        # Verify created_at was set automatically
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT created_at_iso FROM analysis_results 
                WHERE symbol = 'TSLA'
            """)
            created_at_iso = cursor.fetchone()[0]
            
            # Should be a valid ISO timestamp
            assert created_at_iso is not None
            assert "T" in created_at_iso  # ISO format
            assert created_at_iso.endswith("Z")  # UTC timezone
