"""Validate UTC timezone handling end-to-end across the data pipeline."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from data.models import (
    AnalysisResult,
    AnalysisType,
    Holdings,
    NewsEntry,
    NewsItem,
    NewsType,
    PriceData,
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
from data.storage.db_context import _cursor_context


class TestTimezonePipeline:
    """UTC timezone consistency across the data pipeline"""

    @staticmethod
    def _make_entry(
        *,
        symbol: str,
        url: str,
        headline: str,
        source: str,
        published: datetime,
        content: str | None = None,
        news_type: NewsType = NewsType.COMPANY_SPECIFIC,
    ) -> NewsEntry:
        article = NewsItem(
            url=url,
            headline=headline,
            source=source,
            published=published,
            news_type=news_type,
            content=content,
        )
        return NewsEntry(article=article, symbol=symbol, is_important=None)

    def test_timezone_consistency(self, temp_db):
        """UTC normalization in models, storage ISO 'Z', retrieval, and cross-model consistency."""

        # TIMEZONE SCENARIOS TO TEST
        base_dt = datetime(2024, 1, 15, 14, 30, 45)  # Base datetime for testing

        # Scenario 1: Naive datetime (should become UTC via replace)
        naive_dt = base_dt

        # Scenario 2: UTC-aware datetime (should remain UTC)
        utc_aware_dt = base_dt.replace(tzinfo=UTC)

        # Scenario 3: Eastern timezone (should convert to UTC) - EST is UTC-5
        eastern_tz = timezone(timedelta(hours=-5))
        eastern_dt = base_dt.replace(tzinfo=eastern_tz)

        # Scenario 4: Pacific timezone (should convert to UTC) - PST is UTC-8
        pacific_tz = timezone(timedelta(hours=-8))
        pacific_dt = base_dt.replace(tzinfo=pacific_tz)

        # Scenario 5: European timezone (should convert to UTC) - GMT+1 is UTC+1
        london_tz = timezone(timedelta(hours=1))
        london_dt = base_dt.replace(tzinfo=london_tz)

        # Scenario 6: Current datetime (various timezone scenarios)
        current_naive = datetime.now()
        current_utc = datetime.now(UTC)

        # PHASE 1: TEST MODEL __POST_INIT__ NORMALIZATION

        # Test NewsItem normalization
        news_naive = NewsItem(
            url="https://example.com/1",
            headline="Test 1",
            source="Test Source",
            published=naive_dt,
            news_type=NewsType.COMPANY_SPECIFIC,
        )
        news_utc = NewsItem(
            url="https://example.com/2",
            headline="Test 2",
            source="Test Source",
            published=utc_aware_dt,
            news_type=NewsType.COMPANY_SPECIFIC,
        )
        news_eastern = NewsItem(
            url="https://example.com/3",
            headline="Test 3",
            source="Test Source",
            published=eastern_dt,
            news_type=NewsType.COMPANY_SPECIFIC,
        )

        # Verify all NewsItem published times are normalized to UTC
        assert news_naive.published.tzinfo == UTC
        assert news_utc.published.tzinfo == UTC
        assert news_eastern.published.tzinfo == UTC

        # Verify the actual UTC time is correct for timezone-aware inputs
        expected_eastern_utc = eastern_dt.astimezone(UTC)
        assert news_eastern.published == expected_eastern_utc

        # Test PriceData normalization
        price_naive = PriceData(symbol="TEST1", timestamp=naive_dt, price=Decimal("100.00"))
        price_pacific = PriceData(symbol="TEST2", timestamp=pacific_dt, price=Decimal("200.00"))

        # Verify PriceData timestamp normalization
        assert price_naive.timestamp.tzinfo == UTC
        assert price_pacific.timestamp.tzinfo == UTC
        expected_pacific_utc = pacific_dt.astimezone(UTC)
        assert price_pacific.timestamp == expected_pacific_utc

        # Test AnalysisResult normalization (both last_updated and created_at)
        analysis_mixed = AnalysisResult(
            symbol="TEST1",
            analysis_type=AnalysisType.NEWS_ANALYSIS,
            model_name="test-model",
            stance=Stance.BULL,
            confidence_score=0.85,
            last_updated=london_dt,
            created_at=naive_dt,
            result_json='{"test": "data"}',
        )

        # Verify AnalysisResult datetime normalization
        assert analysis_mixed.last_updated.tzinfo == UTC
        assert analysis_mixed.created_at.tzinfo == UTC
        expected_london_utc = london_dt.astimezone(UTC)
        assert analysis_mixed.last_updated == expected_london_utc

        # Test Holdings normalization (both created_at and updated_at)
        holdings_mixed = Holdings(
            symbol="TEST1",
            quantity=Decimal("100"),
            break_even_price=Decimal("150.00"),
            total_cost=Decimal("15000.00"),
            created_at=eastern_dt,
            updated_at=naive_dt,
        )

        # Verify Holdings datetime normalization
        assert holdings_mixed.created_at.tzinfo == UTC
        assert holdings_mixed.updated_at.tzinfo == UTC
        assert holdings_mixed.created_at == expected_eastern_utc

        # PHASE 2: TEST STORAGE ISO FORMAT WITH 'Z' SUFFIX

        # Store all test data and verify ISO format in database
        test_news = [
            self._make_entry(
                symbol="TZ1",
                url="https://example.com/tz1",
                headline="Timezone Test 1",
                source="Test",
                published=naive_dt,
            ),
            self._make_entry(
                symbol="TZ2",
                url="https://example.com/tz2",
                headline="Timezone Test 2",
                source="Test",
                published=eastern_dt,
            ),
            self._make_entry(
                symbol="TZ3",
                url="https://example.com/tz3",
                headline="Timezone Test 3",
                source="Test",
                published=current_utc,
            ),
        ]

        test_prices = [
            PriceData(symbol="TZ1", timestamp=naive_dt, price=Decimal("100.00")),
            PriceData(symbol="TZ2", timestamp=pacific_dt, price=Decimal("200.00")),
            PriceData(symbol="TZ3", timestamp=current_naive, price=Decimal("300.00")),
        ]

        test_analysis = [
            AnalysisResult(
                symbol="TZ1",
                analysis_type=AnalysisType.NEWS_ANALYSIS,
                model_name="test-model",
                stance=Stance.BULL,
                confidence_score=0.85,
                last_updated=london_dt,
                created_at=naive_dt,
                result_json='{"test": "data1"}',
            ),
            AnalysisResult(
                symbol="TZ2",
                analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
                model_name="test-model",
                stance=Stance.NEUTRAL,
                confidence_score=0.75,
                last_updated=current_utc,
                created_at=eastern_dt,
                result_json='{"test": "data2"}',
            ),
        ]

        test_holdings = [
            Holdings(
                symbol="TZ1",
                quantity=Decimal("100"),
                break_even_price=Decimal("150.00"),
                total_cost=Decimal("15000.00"),
                created_at=pacific_dt,
                updated_at=naive_dt,
            ),
            Holdings(
                symbol="TZ2",
                quantity=Decimal("200"),
                break_even_price=Decimal("250.00"),
                total_cost=Decimal("50000.00"),
                created_at=current_utc,
                updated_at=london_dt,
            ),
        ]

        # Store all data
        store_news_items(temp_db, test_news)
        store_price_data(temp_db, test_prices)
        for analysis in test_analysis:
            upsert_analysis_result(temp_db, analysis)
        for holdings in test_holdings:
            upsert_holdings(temp_db, holdings)

        # PHASE 3: VERIFY RAW DATABASE STORAGE HAS 'Z' SUFFIX

        with _cursor_context(temp_db, commit=False) as cursor:
            # Check news_items table
            cursor.execute(
                """
                SELECT ns.symbol, ni.published_iso
                FROM news_items AS ni
                JOIN news_symbols AS ns ON ns.url = ni.url
                WHERE ns.symbol LIKE 'TZ%'
                ORDER BY ns.symbol
                """
            )
            for _symbol, published_iso in cursor.fetchall():
                assert published_iso.endswith("Z")
                assert "T" in published_iso

            # Check price_data table
            cursor.execute(
                "SELECT symbol, timestamp_iso FROM price_data "
                "WHERE symbol LIKE 'TZ%' ORDER BY symbol"
            )
            price_rows = cursor.fetchall()
            for _symbol, timestamp_iso in price_rows:
                assert timestamp_iso.endswith("Z")
                assert "T" in timestamp_iso

            # Check analysis_results table
            cursor.execute(
                "SELECT symbol, last_updated_iso, created_at_iso FROM analysis_results "
                "WHERE symbol LIKE 'TZ%' ORDER BY symbol"
            )
            analysis_rows = cursor.fetchall()
            for _symbol, last_updated_iso, created_at_iso in analysis_rows:
                assert last_updated_iso.endswith("Z")
                assert created_at_iso.endswith("Z")

            # Check holdings table
            cursor.execute(
                "SELECT symbol, created_at_iso, updated_at_iso FROM holdings "
                "WHERE symbol LIKE 'TZ%' ORDER BY symbol"
            )
            holdings_rows = cursor.fetchall()
            for _symbol, created_at_iso, updated_at_iso in holdings_rows:
                assert created_at_iso.endswith("Z")
                assert updated_at_iso.endswith("Z")

        # PHASE 4: TEST QUERY FUNCTIONS RETURN UTC-CONSISTENT DATA

        # Query all data back
        retrieved_news = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        retrieved_prices = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        retrieved_analysis = get_analysis_results(temp_db)
        retrieved_holdings = get_all_holdings(temp_db)

        # Filter to our test data
        tz_news = [item for item in retrieved_news if item.symbol.startswith("TZ")]
        tz_prices = [item for item in retrieved_prices if item.symbol.startswith("TZ")]
        tz_analysis = [item for item in retrieved_analysis if item.symbol.startswith("TZ")]
        tz_holdings = [item for item in retrieved_holdings if item.symbol.startswith("TZ")]

        # Verify all retrieved timestamps are properly formatted ISO with 'Z'
        for item in tz_news:
            assert isinstance(item.published, datetime) and item.published.tzinfo == UTC

        for item in tz_prices:
            assert isinstance(item.timestamp, datetime) and item.timestamp.tzinfo == UTC

        for item in tz_analysis:
            assert isinstance(item.last_updated, datetime) and item.last_updated.tzinfo == UTC
            assert isinstance(item.created_at, datetime) and item.created_at.tzinfo == UTC

        for item in tz_holdings:
            assert isinstance(item.created_at, datetime) and item.created_at.tzinfo == UTC
            assert isinstance(item.updated_at, datetime) and item.updated_at.tzinfo == UTC

        # PHASE 5: TEST CROSS-MODEL CONSISTENCY WITH SAME TIMESTAMP

        # Create a specific timestamp for consistency testing
        consistency_timestamp = datetime(2024, 2, 20, 16, 45, 30, tzinfo=UTC)
        consistency_symbol = "CONSISTENCY_TEST"

        # Create all models with the same timestamp
        consistency_news = self._make_entry(
            symbol=consistency_symbol,
            url="https://example.com/consistency",
            headline="Consistency Test",
            source="Test Source",
            published=consistency_timestamp,
        )

        consistency_price = PriceData(
            symbol=consistency_symbol,
            timestamp=consistency_timestamp,
            price=Decimal("500.00"),
            volume=1000,
        )

        consistency_analysis = AnalysisResult(
            symbol=consistency_symbol,
            analysis_type=AnalysisType.HEAD_TRADER,
            model_name="consistency-model",
            stance=Stance.BULL,
            confidence_score=0.9,
            last_updated=consistency_timestamp,
            created_at=consistency_timestamp,
            result_json='{"consistency": "test"}',
        )

        consistency_holdings = Holdings(
            symbol=consistency_symbol,
            quantity=Decimal("50"),
            break_even_price=Decimal("500.00"),
            total_cost=Decimal("25000.00"),
            created_at=consistency_timestamp,
            updated_at=consistency_timestamp,
        )

        # Store consistency test data
        store_news_items(temp_db, [consistency_news])
        store_price_data(temp_db, [consistency_price])
        upsert_analysis_result(temp_db, consistency_analysis)
        upsert_holdings(temp_db, consistency_holdings)

        # Query back consistency data
        consistency_news_result = [
            item
            for item in get_news_since(temp_db, datetime(2024, 2, 1, tzinfo=UTC))
            if item.symbol == consistency_symbol
        ]
        consistency_price_result = [
            item
            for item in get_price_data_since(temp_db, datetime(2024, 2, 1, tzinfo=UTC))
            if item.symbol == consistency_symbol
        ]
        consistency_analysis_result = get_analysis_results(temp_db, symbol=consistency_symbol)
        consistency_holdings_result = [
            item for item in get_all_holdings(temp_db) if item.symbol == consistency_symbol
        ]

        # Verify all have the same timestamp representation
        expected_dt = datetime(2024, 2, 20, 16, 45, 30, tzinfo=UTC)

        assert len(consistency_news_result) == 1
        assert consistency_news_result[0].published == expected_dt

        assert len(consistency_price_result) == 1
        assert consistency_price_result[0].timestamp == expected_dt

        assert len(consistency_analysis_result) == 1
        assert consistency_analysis_result[0].last_updated == expected_dt
        assert consistency_analysis_result[0].created_at == expected_dt

        assert len(consistency_holdings_result) == 1
        assert consistency_holdings_result[0].created_at == expected_dt
        assert consistency_holdings_result[0].updated_at == expected_dt

        # PHASE 6: TEST BOUNDARY TIMEZONE SCENARIOS

        # Test timezone conversion with UTC-4 (Eastern Daylight Time)
        edt_tz = timezone(timedelta(hours=-4))
        test_time = datetime(2024, 3, 10, 2, 30, tzinfo=edt_tz)  # UTC-4 timezone conversion

        boundary_news = self._make_entry(
            symbol="BOUNDARY",
            url="https://example.com/boundary",
            headline="Boundary Test",
            source="Test Source",
            published=test_time,
        )

        store_news_items(temp_db, [boundary_news])
        boundary_result = [
            item
            for item in get_news_since(temp_db, datetime(2024, 3, 1, tzinfo=UTC))
            if item.symbol == "BOUNDARY"
        ]

        assert len(boundary_result) == 1
        assert isinstance(boundary_result[0].published, datetime)
        assert boundary_result[0].published.tzinfo == UTC
