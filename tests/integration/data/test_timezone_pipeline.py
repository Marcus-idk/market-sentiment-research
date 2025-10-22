"""
Timezone consistency pipeline tests.
Tests UTC timezone handling throughout the complete data pipeline,
from model initialization through storage to retrieval.
"""

from datetime import datetime, timezone, timedelta

from data.storage import store_news_items, store_price_data, upsert_analysis_result, upsert_holdings, get_news_since, get_price_data_since, get_analysis_results, get_all_holdings
from data.storage.db_context import _cursor_context
from data.models import NewsItem, PriceData, AnalysisResult, Holdings, Stance, AnalysisType
from decimal import Decimal


class TestTimezonePipeline:
    """Test UTC timezone consistency throughout the entire data pipeline"""
    
    def test_timezone_consistency(self, temp_db):
        """
        Test UTC timezone consistency throughout the entire pipeline.
        
        Validates:
        1. Model __post_init__ normalization converts all datetime inputs to UTC
        2. Storage _datetime_to_iso function formats as ISO string with 'Z'
        3. Retrieved datetime strings represent correct UTC time
        4. Cross-model consistency with same timestamp
        5. Various timezone scenarios: naive, UTC-aware, non-UTC aware, current time
        
        Tests all models with datetime fields: NewsItem, PriceData, AnalysisResult, Holdings
        """
        
        # TIMEZONE SCENARIOS TO TEST
        base_dt = datetime(2024, 1, 15, 14, 30, 45)  # Base datetime for testing
        
        # Scenario 1: Naive datetime (should become UTC via replace)
        naive_dt = base_dt
        
        # Scenario 2: UTC-aware datetime (should remain UTC)
        utc_aware_dt = base_dt.replace(tzinfo=timezone.utc)
        
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
        current_utc = datetime.now(timezone.utc)
        
        # PHASE 1: TEST MODEL __POST_INIT__ NORMALIZATION
        
        # Test NewsItem normalization
        news_naive = NewsItem(
            symbol="TEST1", url="https://example.com/1", headline="Test 1",
            source="Test Source", published=naive_dt
        )
        news_utc = NewsItem(
            symbol="TEST2", url="https://example.com/2", headline="Test 2", 
            source="Test Source", published=utc_aware_dt
        )
        news_eastern = NewsItem(
            symbol="TEST3", url="https://example.com/3", headline="Test 3",
            source="Test Source", published=eastern_dt
        )
        
        # Verify all NewsItem published times are normalized to UTC
        assert news_naive.published.tzinfo == timezone.utc, "Naive datetime should be converted to UTC"
        assert news_utc.published.tzinfo == timezone.utc, "UTC datetime should remain UTC"
        assert news_eastern.published.tzinfo == timezone.utc, "Eastern datetime should be converted to UTC"
        
        # Verify the actual UTC time is correct for timezone-aware inputs
        expected_eastern_utc = eastern_dt.astimezone(timezone.utc)
        assert news_eastern.published == expected_eastern_utc, f"Eastern time conversion incorrect: expected {expected_eastern_utc}, got {news_eastern.published}"
        
        # Test PriceData normalization
        price_naive = PriceData(
            symbol="TEST1", timestamp=naive_dt, price=Decimal('100.00')
        )
        price_pacific = PriceData(
            symbol="TEST2", timestamp=pacific_dt, price=Decimal('200.00')
        )
        
        # Verify PriceData timestamp normalization
        assert price_naive.timestamp.tzinfo == timezone.utc
        assert price_pacific.timestamp.tzinfo == timezone.utc
        expected_pacific_utc = pacific_dt.astimezone(timezone.utc)
        assert price_pacific.timestamp == expected_pacific_utc
        
        # Test AnalysisResult normalization (both last_updated and created_at)
        analysis_mixed = AnalysisResult(
            symbol="TEST1", analysis_type=AnalysisType.NEWS_ANALYSIS,
            model_name="test-model", stance=Stance.BULL, confidence_score=0.85,
            last_updated=london_dt, created_at=naive_dt, result_json='{"test": "data"}'
        )
        
        # Verify AnalysisResult datetime normalization
        assert analysis_mixed.last_updated.tzinfo == timezone.utc
        assert analysis_mixed.created_at.tzinfo == timezone.utc
        expected_london_utc = london_dt.astimezone(timezone.utc)
        assert analysis_mixed.last_updated == expected_london_utc
        
        # Test Holdings normalization (both created_at and updated_at)
        holdings_mixed = Holdings(
            symbol="TEST1", quantity=Decimal('100'), break_even_price=Decimal('150.00'),
            total_cost=Decimal('15000.00'), created_at=eastern_dt, updated_at=naive_dt
        )
        
        # Verify Holdings datetime normalization
        assert holdings_mixed.created_at.tzinfo == timezone.utc
        assert holdings_mixed.updated_at.tzinfo == timezone.utc
        assert holdings_mixed.created_at == expected_eastern_utc
        
        # PHASE 2: TEST STORAGE ISO FORMAT WITH 'Z' SUFFIX
        
        # Store all test data and verify ISO format in database
        test_news = [
            NewsItem(symbol="TZ1", url="https://example.com/tz1", headline="Timezone Test 1",
                    source="Test", published=naive_dt),
            NewsItem(symbol="TZ2", url="https://example.com/tz2", headline="Timezone Test 2", 
                    source="Test", published=eastern_dt),
            NewsItem(symbol="TZ3", url="https://example.com/tz3", headline="Timezone Test 3",
                    source="Test", published=current_utc)
        ]
        
        test_prices = [
            PriceData(symbol="TZ1", timestamp=naive_dt, price=Decimal('100.00')),
            PriceData(symbol="TZ2", timestamp=pacific_dt, price=Decimal('200.00')),
            PriceData(symbol="TZ3", timestamp=current_naive, price=Decimal('300.00'))
        ]
        
        test_analysis = [
            AnalysisResult(
                symbol="TZ1", analysis_type=AnalysisType.NEWS_ANALYSIS, model_name="test-model",
                stance=Stance.BULL, confidence_score=0.85, last_updated=london_dt,
                created_at=naive_dt, result_json='{"test": "data1"}'
            ),
            AnalysisResult(
                symbol="TZ2", analysis_type=AnalysisType.SENTIMENT_ANALYSIS, model_name="test-model",
                stance=Stance.NEUTRAL, confidence_score=0.75, last_updated=current_utc,
                created_at=eastern_dt, result_json='{"test": "data2"}'
            )
        ]
        
        test_holdings = [
            Holdings(
                symbol="TZ1", quantity=Decimal('100'), break_even_price=Decimal('150.00'),
                total_cost=Decimal('15000.00'), created_at=pacific_dt, updated_at=naive_dt
            ),
            Holdings(
                symbol="TZ2", quantity=Decimal('200'), break_even_price=Decimal('250.00'),
                total_cost=Decimal('50000.00'), created_at=current_utc, updated_at=london_dt
            )
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
            cursor.execute("SELECT symbol, published_iso FROM news_items WHERE symbol LIKE 'TZ%' ORDER BY symbol")
            news_rows = cursor.fetchall()
            for symbol, published_iso in news_rows:
                assert published_iso.endswith('Z'), f"News item {symbol} published_iso should end with 'Z': {published_iso}"
                assert 'T' in published_iso, f"News item {symbol} published_iso should contain 'T': {published_iso}"
            
            # Check price_data table  
            cursor.execute("SELECT symbol, timestamp_iso FROM price_data WHERE symbol LIKE 'TZ%' ORDER BY symbol")
            price_rows = cursor.fetchall()
            for symbol, timestamp_iso in price_rows:
                assert timestamp_iso.endswith('Z'), f"Price data {symbol} timestamp_iso should end with 'Z': {timestamp_iso}"
                assert 'T' in timestamp_iso, f"Price data {symbol} timestamp_iso should contain 'T': {timestamp_iso}"
            
            # Check analysis_results table
            cursor.execute("SELECT symbol, last_updated_iso, created_at_iso FROM analysis_results WHERE symbol LIKE 'TZ%' ORDER BY symbol")
            analysis_rows = cursor.fetchall()
            for symbol, last_updated_iso, created_at_iso in analysis_rows:
                assert last_updated_iso.endswith('Z'), f"Analysis {symbol} last_updated_iso should end with 'Z': {last_updated_iso}"
                assert created_at_iso.endswith('Z'), f"Analysis {symbol} created_at_iso should end with 'Z': {created_at_iso}"
                
            # Check holdings table
            cursor.execute("SELECT symbol, created_at_iso, updated_at_iso FROM holdings WHERE symbol LIKE 'TZ%' ORDER BY symbol")
            holdings_rows = cursor.fetchall()
            for symbol, created_at_iso, updated_at_iso in holdings_rows:
                assert created_at_iso.endswith('Z'), f"Holdings {symbol} created_at_iso should end with 'Z': {created_at_iso}"
                assert updated_at_iso.endswith('Z'), f"Holdings {symbol} updated_at_iso should end with 'Z': {updated_at_iso}"
        
        # PHASE 4: TEST QUERY FUNCTIONS RETURN UTC-CONSISTENT DATA
        
        # Query all data back
        retrieved_news = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        retrieved_prices = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        retrieved_analysis = get_analysis_results(temp_db)
        retrieved_holdings = get_all_holdings(temp_db)
        
        # Filter to our test data
        tz_news = [item for item in retrieved_news if item.symbol.startswith('TZ')]
        tz_prices = [item for item in retrieved_prices if item.symbol.startswith('TZ')]
        tz_analysis = [item for item in retrieved_analysis if item.symbol.startswith('TZ')]
        tz_holdings = [item for item in retrieved_holdings if item.symbol.startswith('TZ')]
        
        # Verify all retrieved timestamps are properly formatted ISO with 'Z'
        for item in tz_news:
            assert isinstance(item.published, datetime) and item.published.tzinfo == timezone.utc, f"Retrieved news published_iso should end with 'Z': {item.published}"
            
        for item in tz_prices:
            assert isinstance(item.timestamp, datetime) and item.timestamp.tzinfo == timezone.utc, f"Retrieved price timestamp_iso should end with 'Z': {item.timestamp}"
            
        for item in tz_analysis:
            assert isinstance(item.last_updated, datetime) and item.last_updated.tzinfo == timezone.utc, f"Retrieved analysis last_updated_iso should end with 'Z': {item.last_updated}"
            assert isinstance(item.created_at, datetime) and item.created_at.tzinfo == timezone.utc, f"Retrieved analysis created_at_iso should end with 'Z': {item.created_at}"
            
        for item in tz_holdings:
            assert isinstance(item.created_at, datetime) and item.created_at.tzinfo == timezone.utc, f"Retrieved holdings created_at_iso should end with 'Z': {item.created_at}"
            assert isinstance(item.updated_at, datetime) and item.updated_at.tzinfo == timezone.utc, f"Retrieved holdings updated_at_iso should end with 'Z': {item.updated_at}"
        
        # PHASE 5: TEST CROSS-MODEL CONSISTENCY WITH SAME TIMESTAMP
        
        # Create a specific timestamp for consistency testing
        consistency_timestamp = datetime(2024, 2, 20, 16, 45, 30, tzinfo=timezone.utc)
        consistency_symbol = "CONSISTENCY_TEST"
        
        # Create all models with the same timestamp
        consistency_news = NewsItem(
            symbol=consistency_symbol, url="https://example.com/consistency",
            headline="Consistency Test", source="Test Source", published=consistency_timestamp
        )
        
        consistency_price = PriceData(
            symbol=consistency_symbol, timestamp=consistency_timestamp,
            price=Decimal('500.00'), volume=1000
        )
        
        consistency_analysis = AnalysisResult(
            symbol=consistency_symbol, analysis_type=AnalysisType.HEAD_TRADER,
            model_name="consistency-model", stance=Stance.BULL, confidence_score=0.9,
            last_updated=consistency_timestamp, created_at=consistency_timestamp,
            result_json='{"consistency": "test"}'
        )
        
        consistency_holdings = Holdings(
            symbol=consistency_symbol, quantity=Decimal('50'), break_even_price=Decimal('500.00'),
            total_cost=Decimal('25000.00'), created_at=consistency_timestamp, 
            updated_at=consistency_timestamp
        )
        
        # Store consistency test data
        store_news_items(temp_db, [consistency_news])
        store_price_data(temp_db, [consistency_price])
        upsert_analysis_result(temp_db, consistency_analysis)
        upsert_holdings(temp_db, consistency_holdings)
        
        # Query back consistency data
        consistency_news_result = [item for item in get_news_since(temp_db, datetime(2024, 2, 1, tzinfo=timezone.utc)) 
                                 if item.symbol == consistency_symbol]
        consistency_price_result = [item for item in get_price_data_since(temp_db, datetime(2024, 2, 1, tzinfo=timezone.utc))
                                  if item.symbol == consistency_symbol]
        consistency_analysis_result = get_analysis_results(temp_db, symbol=consistency_symbol)
        consistency_holdings_result = [item for item in get_all_holdings(temp_db) 
                                     if item.symbol == consistency_symbol]
        
        # Verify all have the same timestamp representation
        expected_dt = datetime(2024, 2, 20, 16, 45, 30, tzinfo=timezone.utc)
        
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
        
        boundary_news = NewsItem(
            symbol="BOUNDARY", url="https://example.com/boundary", headline="Boundary Test",
            source="Test Source", published=test_time
        )
        
        store_news_items(temp_db, [boundary_news])
        boundary_result = [item for item in get_news_since(temp_db, datetime(2024, 3, 1, tzinfo=timezone.utc))
                         if item.symbol == 'BOUNDARY']
        
        assert len(boundary_result) == 1
        # Timezone conversion should be properly handled and stored as UTC
        assert isinstance(boundary_result[0].published, datetime) and boundary_result[0].published.tzinfo == timezone.utc
        