"""
Tests analysis result storage operations and conflict resolution.
"""

from datetime import UTC, datetime

from data.models import AnalysisResult, AnalysisType, Stance
from data.storage import upsert_analysis_result
from data.storage.db_context import _cursor_context


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
            last_updated=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            result_json='{"sentiment": "positive"}',
            created_at=datetime(2024, 1, 15, 9, 0, tzinfo=UTC),
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
            last_updated=datetime(2024, 1, 15, 11, 0, tzinfo=UTC),  # Should update
            result_json='{"sentiment": "neutral"}',  # Should update
            created_at=datetime(
                2024, 1, 15, 10, 0, tzinfo=UTC
            ),  # Should be ignored (preserve original)
        )

        # Upsert updated result
        upsert_analysis_result(temp_db, result2)

        # Verify record was updated, not duplicated
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("""
                SELECT COUNT(*), model_name, stance, confidence_score,
                       last_updated_iso, result_json, created_at_iso
                FROM analysis_results
                WHERE symbol = 'AAPL' AND analysis_type = 'news_analysis'
            """)
            count, model, stance, confidence, updated, json_result, created = cursor.fetchone()

            assert count == 1, "should not duplicate row on conflict"
            assert model == "gpt-4o"
            assert stance == "NEUTRAL"
            assert confidence == 0.75
            assert updated == "2024-01-15T11:00:00Z", "upsert should update last_updated"
            assert json_result == '{"sentiment": "neutral"}'
            assert created == "2024-01-15T09:00:00Z", "upsert should preserve created_at"

    def test_upsert_analysis_auto_created_at(self, temp_db):
        """Test automatic created_at when not provided"""
        # Analysis result without created_at
        result = AnalysisResult(
            symbol="TSLA",
            analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
            model_name="claude-3",
            stance=Stance.BEAR,
            confidence_score=0.90,
            last_updated=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            result_json='{"sentiment": "bearish"}',
            # created_at not provided
        )

        # Store result
        upsert_analysis_result(temp_db, result)

        # Verify created_at was set automatically
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("""
                SELECT created_at_iso FROM analysis_results
                WHERE symbol = 'TSLA'
            """)
            created_at_iso = cursor.fetchone()[0]

            # Should be a valid ISO timestamp
            assert created_at_iso is not None
            assert "T" in created_at_iso  # ISO format
            assert created_at_iso.endswith("Z")  # UTC timezone
