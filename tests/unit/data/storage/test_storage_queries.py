"""
Tests data retrieval queries and filtering logic.
"""

from datetime import UTC, datetime
from decimal import Decimal

from data.models import (
    AnalysisResult,
    AnalysisType,
    Holdings,
    NewsEntry,
    NewsItem,
    NewsType,
    PriceData,
    Session,
    Stance,
)
from data.storage import (
    get_all_holdings,
    get_analysis_results,
    get_news_since,
    get_price_data_since,
    store_news_items,
    store_price_data,
    upsert_analysis_result,
    upsert_holdings,
)


class TestQueryOperations:
    """Test data query operations"""

    def test_get_news_since_timestamp_filtering(self, temp_db):
        """Test news retrieval with timestamp filtering"""
        # Store news items with different timestamps
        entries = [
            NewsEntry(
                article=NewsItem(
                    url="https://example.com/1",
                    headline="Old News",
                    source="Reuters",
                    published=datetime(2024, 1, 10, 10, 0, tzinfo=UTC),
                    news_type=NewsType.COMPANY_SPECIFIC,
                ),
                symbol="AAPL",
                is_important=None,
            ),
            NewsEntry(
                article=NewsItem(
                    url="https://example.com/2",
                    headline="Recent News",
                    source="Reuters",
                    published=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                    news_type=NewsType.COMPANY_SPECIFIC,
                ),
                symbol="AAPL",
                is_important=True,
            ),
            NewsEntry(
                article=NewsItem(
                    url="https://example.com/3",
                    headline="Tesla News",
                    source="Reuters",
                    published=datetime(2024, 1, 20, 10, 0, tzinfo=UTC),
                    news_type=NewsType.COMPANY_SPECIFIC,
                ),
                symbol="TSLA",
                is_important=False,
            ),
        ]

        store_news_items(temp_db, entries)

        # Query news since 2024-01-12 (should get 2 items)
        since = datetime(2024, 1, 12, 0, 0, tzinfo=UTC)
        results = get_news_since(temp_db, since)

        assert len(results) == 2

        # Verify results are ordered by published time
        assert results[0].headline == "Recent News"
        assert results[1].headline == "Tesla News"

        # Verify all expected fields are present
        for result in results:
            assert result.symbol in {"AAPL", "TSLA"}
            assert result.url.startswith("https://example.com/")
            assert result.source == "Reuters"
            assert result.news_type is NewsType.COMPANY_SPECIFIC

    def test_get_price_data_since_ordering(self, temp_db):
        """Test price data retrieval with proper ordering"""
        # Store price data in random order
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                price=Decimal("150.00"),
                session=Session.REG,
            ),
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 9, 0, tzinfo=UTC),
                price=Decimal("149.00"),
                session=Session.PRE,
            ),
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                price=Decimal("151.00"),
                session=Session.POST,
            ),
        ]

        store_price_data(temp_db, items)

        # Query all price data
        since = datetime(2024, 1, 15, 0, 0, tzinfo=UTC)
        results = get_price_data_since(temp_db, since)

        assert len(results) == 3

        # Verify chronological ordering
        assert results[0].timestamp == datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
        assert results[1].timestamp == datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        assert results[2].timestamp == datetime(2024, 1, 15, 11, 0, tzinfo=UTC)

        # Verify all fields present
        for result in results:
            assert hasattr(result, "symbol")
            assert hasattr(result, "timestamp")
            assert hasattr(result, "price")
            assert hasattr(result, "volume")
            assert hasattr(result, "session")

    def test_get_all_holdings_ordering(self, temp_db):
        """Test holdings retrieval with symbol ordering"""
        # Store holdings in random symbol order
        holdings_list = [
            Holdings(
                symbol="TSLA",
                quantity=Decimal("50"),
                break_even_price=Decimal("200.00"),
                total_cost=Decimal("10000.00"),
            ),
            Holdings(
                symbol="AAPL",
                quantity=Decimal("100"),
                break_even_price=Decimal("150.00"),
                total_cost=Decimal("15000.00"),
            ),
            Holdings(
                symbol="MSFT",
                quantity=Decimal("75"),
                break_even_price=Decimal("300.00"),
                total_cost=Decimal("22500.00"),
            ),
        ]

        for holdings in holdings_list:
            upsert_holdings(temp_db, holdings)

        # Query all holdings
        results = get_all_holdings(temp_db)

        assert len(results) == 3

        # Verify alphabetical symbol ordering
        symbols = [result.symbol for result in results]
        assert symbols == ["AAPL", "MSFT", "TSLA"]

        # Verify all fields present
        for result in results:
            assert hasattr(result, "symbol")
            assert hasattr(result, "quantity")
            assert hasattr(result, "break_even_price")
            assert hasattr(result, "total_cost")
            assert hasattr(result, "notes")
            assert hasattr(result, "created_at")
            assert hasattr(result, "updated_at")

    def test_get_analysis_results_symbol_filtering(self, temp_db):
        """Test analysis results retrieval with optional symbol filtering"""
        # Store analysis results for multiple symbols
        results = [
            AnalysisResult(
                symbol="AAPL",
                analysis_type=AnalysisType.NEWS_ANALYSIS,
                model_name="gpt-4",
                stance=Stance.BULL,
                confidence_score=0.85,
                last_updated=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                result_json='{"sentiment": "positive"}',
            ),
            AnalysisResult(
                symbol="AAPL",
                analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
                model_name="claude-3",
                stance=Stance.NEUTRAL,
                confidence_score=0.75,
                last_updated=datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                result_json='{"sentiment": "neutral"}',
            ),
            AnalysisResult(
                symbol="TSLA",
                analysis_type=AnalysisType.NEWS_ANALYSIS,
                model_name="gpt-4",
                stance=Stance.BEAR,
                confidence_score=0.90,
                last_updated=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
                result_json='{"sentiment": "bearish"}',
            ),
        ]

        for result in results:
            upsert_analysis_result(temp_db, result)

        # Test filtering by symbol
        aapl_results = get_analysis_results(temp_db, symbol="AAPL")
        assert len(aapl_results) == 2

        # Verify correct symbol filtering
        for result in aapl_results:
            assert result.symbol == "AAPL"

        # Test getting all results (no filter)
        all_results = get_analysis_results(temp_db)
        assert len(all_results) == 3

        # Verify ordering (symbol ASC, analysis_type ASC)
        symbols_and_types = [(r.symbol, r.analysis_type.value) for r in all_results]
        expected = [
            ("AAPL", "news_analysis"),
            ("AAPL", "sentiment_analysis"),
            ("TSLA", "news_analysis"),
        ]
        assert symbols_and_types == expected
