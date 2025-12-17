"""Validate schema CHECK constraints and transaction rollback behavior."""

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data.models import AnalysisResult, AnalysisType, Holdings, PriceData, Session, Stance
from data.storage import (
    get_all_holdings,
    get_analysis_results,
    get_price_data_since,
    store_price_data,
    upsert_analysis_result,
    upsert_holdings,
)
from data.storage.db_context import _cursor_context


class TestSchemaConstraints:
    """Database constraint validation and rollback behavior"""

    def test_transaction_rollback_on_constraint_violation(self, temp_db):
        """Constraint violations raise and do not corrupt DB; valid ops succeed."""
        test_timestamp = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

        # ========================================
        # STEP 1: INSERT VALID BASELINE DATA
        # ========================================

        # Valid PriceData
        valid_price_data = [
            PriceData(
                symbol="AAPL",
                timestamp=test_timestamp,
                price=Decimal("150.00"),
                volume=1000000,
                session=Session.REG,
            )
        ]
        store_price_data(temp_db, valid_price_data)

        # Valid AnalysisResult
        valid_analysis = AnalysisResult(
            symbol="AAPL",
            analysis_type=AnalysisType.NEWS_ANALYSIS,
            model_name="gpt-4o",
            stance=Stance.BULL,
            confidence_score=0.85,
            last_updated=test_timestamp,
            result_json='{"sentiment": "positive", "key_factors": ["strong earnings"]}',
        )
        upsert_analysis_result(temp_db, valid_analysis)

        # Valid Holdings
        valid_holdings = Holdings(
            symbol="AAPL",
            quantity=Decimal("100"),
            break_even_price=Decimal("150.00"),
            total_cost=Decimal("15000.00"),
            created_at=test_timestamp,
            updated_at=test_timestamp,
        )
        upsert_holdings(temp_db, valid_holdings)

        # Verify baseline data is stored
        price_results = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        analysis_results = get_analysis_results(temp_db, "AAPL")
        holdings_results = get_all_holdings(temp_db)

        assert len(price_results) == 1
        assert len(analysis_results) == 1
        assert len(holdings_results) == 1

        baseline_price = price_results[0]
        baseline_analysis = analysis_results[0]
        baseline_holdings = holdings_results[0]

        # ========================================
        # STEP 2: TEST PRICE_DATA CONSTRAINTS
        # ========================================

        # Test 2a: Negative price violation (CHECK price > 0)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO price_data (symbol, timestamp_iso, price, volume, session)
                VALUES (?, ?, ?, ?, ?)
            """,
                ("TSLA", "2024-01-15T13:00:00Z", "-50.00", 1000, "REG"),
            )

        # Test 2b: Negative volume violation (CHECK volume >= 0)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO price_data (symbol, timestamp_iso, price, volume, session)
                VALUES (?, ?, ?, ?, ?)
            """,
                ("MSFT", "2024-01-15T13:00:00Z", "100.00", -1000, "REG"),
            )

        # Test 2c: Invalid session enum violation
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO price_data (symbol, timestamp_iso, price, volume, session)
                VALUES (?, ?, ?, ?, ?)
            """,
                ("GOOGL", "2024-01-15T13:00:00Z", "100.00", 1000, "INVALID_SESSION"),
            )

        # ========================================
        # STEP 3: TEST ANALYSIS_RESULTS CONSTRAINTS
        # ========================================

        # Test 3a: confidence_score below 0 (CHECK confidence_score BETWEEN 0 AND 1)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    symbol,
                    analysis_type,
                    model_name,
                    stance,
                    confidence_score,
                    last_updated_iso,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "TSLA",
                    "news_analysis",
                    "gpt-4",
                    "BULL",
                    -0.1,
                    "2024-01-15T13:00:00Z",
                    '{"test": "data"}',
                ),
            )

        # Test 3b: confidence_score above 1 (CHECK confidence_score BETWEEN 0 AND 1)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    symbol,
                    analysis_type,
                    model_name,
                    stance,
                    confidence_score,
                    last_updated_iso,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "MSFT",
                    "sentiment_analysis",
                    "claude-3",
                    "BEAR",
                    1.5,
                    "2024-01-15T13:00:00Z",
                    '{"test": "data"}',
                ),
            )

        # Test 3c: Invalid stance enum
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    symbol,
                    analysis_type,
                    model_name,
                    stance,
                    confidence_score,
                    last_updated_iso,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "GOOGL",
                    "news_analysis",
                    "gpt-4",
                    "INVALID_STANCE",
                    0.5,
                    "2024-01-15T13:00:00Z",
                    '{"test": "data"}',
                ),
            )

        # Test 3d: Invalid analysis_type enum
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    symbol,
                    analysis_type,
                    model_name,
                    stance,
                    confidence_score,
                    last_updated_iso,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "NVDA",
                    "invalid_analysis",
                    "gpt-4",
                    "NEUTRAL",
                    0.5,
                    "2024-01-15T13:00:00Z",
                    '{"test": "data"}',
                ),
            )

        # Test 3e: Invalid JSON format (not valid JSON)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    symbol,
                    analysis_type,
                    model_name,
                    stance,
                    confidence_score,
                    last_updated_iso,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "META",
                    "news_analysis",
                    "gpt-4",
                    "BULL",
                    0.8,
                    "2024-01-15T13:00:00Z",
                    "{invalid json format",
                ),
            )

        # Test 3f: JSON array instead of object (must be object)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO analysis_results (
                    symbol,
                    analysis_type,
                    model_name,
                    stance,
                    confidence_score,
                    last_updated_iso,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "AMD",
                    "sentiment_analysis",
                    "claude-3",
                    "NEUTRAL",
                    0.6,
                    "2024-01-15T13:00:00Z",
                    '["this", "is", "array"]',
                ),
            )

        # ========================================
        # STEP 4: TEST HOLDINGS CONSTRAINTS
        # ========================================

        # Test 4a: Negative quantity (CHECK quantity > 0)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                VALUES (?, ?, ?, ?)
            """,
                ("TSLA", "-100.0", "200.00", "20000.00"),
            )

        # Test 4b: Zero break_even_price (CHECK break_even_price > 0)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                VALUES (?, ?, ?, ?)
            """,
                ("MSFT", "50.0", "0.0", "5000.00"),
            )

        # Test 4c: Negative total_cost (CHECK total_cost > 0)
        with (
            pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
            _cursor_context(temp_db) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO holdings (symbol, quantity, break_even_price, total_cost)
                VALUES (?, ?, ?, ?)
            """,
                ("GOOGL", "25.0", "100.00", "-2500.00"),
            )

        # ========================================
        # STEP 5: VERIFY DATABASE STATE UNCHANGED (ROLLBACK OCCURRED)
        # ========================================

        # Re-query all data after constraint violations
        final_price_results = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        final_analysis_results = get_analysis_results(temp_db)
        final_holdings_results = get_all_holdings(temp_db)

        # Verify original data still exists and unchanged
        assert len(final_price_results) == 1
        assert len(final_analysis_results) == 1
        assert len(final_holdings_results) == 1

        # Verify all baseline data is identical (no corruption)
        assert final_price_results[0] == baseline_price
        assert final_analysis_results[0] == baseline_analysis
        assert final_holdings_results[0] == baseline_holdings

        # ========================================
        # STEP 6: VERIFY SUBSEQUENT VALID OPERATIONS WORK (DATABASE INTEGRITY MAINTAINED)
        # ========================================

        # Insert new valid PriceData for different symbol
        new_valid_price = [
            PriceData(
                symbol="TSLA",
                timestamp=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
                price=Decimal("200.00"),
                volume=500000,
                session=Session.POST,
            )
        ]
        store_price_data(temp_db, new_valid_price)

        # Insert new valid AnalysisResult
        new_valid_analysis = AnalysisResult(
            symbol="TSLA",
            analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
            model_name="claude-3-5-sonnet",
            stance=Stance.NEUTRAL,
            confidence_score=0.75,
            last_updated=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
            result_json='{"sentiment": "neutral", "volatility": "high"}',
        )
        upsert_analysis_result(temp_db, new_valid_analysis)

        # Insert new valid Holdings
        new_valid_holdings = Holdings(
            symbol="MSFT",
            quantity=Decimal("75"),
            break_even_price=Decimal("300.00"),
            total_cost=Decimal("22500.00"),
            notes="New position after constraint test",
        )
        upsert_holdings(temp_db, new_valid_holdings)

        # Verify all valid operations succeeded
        updated_price_results = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        updated_analysis_results = get_analysis_results(temp_db)
        updated_holdings_results = get_all_holdings(temp_db)

        # Should now have 2 records each (original + new)
        assert len(updated_price_results) == 2
        assert len(updated_analysis_results) == 2
        assert len(updated_holdings_results) == 2

        # Verify new TSLA price data was stored correctly
        tsla_price = next((p for p in updated_price_results if p.symbol == "TSLA"), None)
        assert tsla_price is not None
        assert tsla_price.price == Decimal("200.00")
        assert tsla_price.session == Session.POST

        # Verify new TSLA analysis was stored correctly
        tsla_analysis = next((a for a in updated_analysis_results if a.symbol == "TSLA"), None)
        assert tsla_analysis is not None
        assert tsla_analysis.stance == Stance.NEUTRAL
        assert tsla_analysis.confidence_score == 0.75

        # Verify new MSFT holdings was stored correctly
        msft_holdings = next((h for h in updated_holdings_results if h.symbol == "MSFT"), None)
        assert msft_holdings is not None
        assert msft_holdings.quantity == Decimal("75")
        assert msft_holdings.notes == "New position after constraint test"

        # Final verification: Original AAPL data still intact
        aapl_price = next((p for p in updated_price_results if p.symbol == "AAPL"), None)
        aapl_analysis = next((a for a in updated_analysis_results if a.symbol == "AAPL"), None)
        aapl_holdings = next((h for h in updated_holdings_results if h.symbol == "AAPL"), None)

        assert aapl_price == baseline_price
        assert aapl_analysis == baseline_analysis
        assert aapl_holdings == baseline_holdings
