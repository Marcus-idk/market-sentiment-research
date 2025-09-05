"""
Storage operations tests.
Tests CRUD operations, type conversions, and SQLite database functionality.
Uses Windows-safe cleanup patterns for WAL mode databases.
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
import os
from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)


class TestDatabaseInitialization:
    """Test database initialization and schema setup"""
    
    def test_init_database_creates_schema(self, temp_db_path):
        """Test database initialization creates all required tables"""
        # Initialize database
        init_database(temp_db_path)
        
        # Verify all 4 tables were created
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Check table existence
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            tables = {row[0] for row in cursor.fetchall()}
            
            required_tables = {'analysis_results', 'holdings', 'news_items', 'price_data'}
            assert required_tables.issubset(tables), f"Required tables {required_tables} not found. Got: {tables}"
    
    def test_schema_file_not_found_raises_error(self, temp_db_path, monkeypatch):
        """Test FileNotFoundError when schema.sql is missing"""
        # Monkeypatch os.path.exists to simulate missing schema.sql
        original_exists = os.path.exists
        monkeypatch.setattr(os.path, 'exists', 
            lambda path: False if 'schema.sql' in path else original_exists(path))
        
        with pytest.raises(FileNotFoundError, match="Schema file not found"):
            init_database(temp_db_path)
    
    def test_wal_mode_enabled(self, temp_db):
        """Test WAL mode is properly enabled (requires file-backed DB)"""
        # Check WAL mode is enabled (database already initialized by fixture)
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == 'wal', f"Expected WAL mode, got {mode}"


class TestURLNormalization:
    """Test URL normalization for cross-provider deduplication"""
    
    def test_normalize_url_strips_tracking_parameters(self):
        """Test removal of common tracking parameters (case-insensitive)"""
        test_cases = [
            # UTM parameters
            ("https://example.com?utm_source=google&utm_medium=cpc", 
             "https://example.com"),
            ("https://example.com?utm_campaign=test&utm_term=keyword", 
             "https://example.com"),
            ("https://example.com?utm_content=banner&other=keep", 
             "https://example.com?other=keep"),
             
            # Other tracking parameters
            ("https://example.com?ref=twitter&fbclid=abc123", 
             "https://example.com"),
            ("https://example.com?gclid=xyz789&msclkid=def456", 
             "https://example.com"),
            ("https://example.com?source=newsletter&campaign=promo", 
             "https://example.com?source=newsletter"),
             
            # Case insensitive removal
            ("https://example.com?UTM_Source=google&CAMPAIGN=test", 
             "https://example.com"),
            ("https://example.com?REF=twitter&Source=email", 
             "https://example.com?Source=email"),
        ]
        
        for original, expected in test_cases:
            result = _normalize_url(original)
            assert result == expected, f"Failed for {original}: expected {expected}, got {result}"
    
    def test_normalize_url_preserves_essential_parameters(self):
        """Test non-tracking parameters are preserved"""
        test_cases = [
            ("https://example.com?id=123&page=2", 
             "https://example.com?id=123&page=2"),
            ("https://example.com?q=search&sort=date", 
             "https://example.com?q=search&sort=date"),
            ("https://example.com?article=news&category=tech", 
             "https://example.com?article=news&category=tech"),
        ]
        
        for original, expected in test_cases:
            result = _normalize_url(original)
            assert result == expected, f"Failed for {original}: expected {expected}, got {result}"
    
    def test_normalize_url_canonical_ordering(self):
        """Test consistent parameter ordering"""
        # Parameters should be sorted for consistent results
        original = "https://example.com?z=last&a=first&m=middle"
        result = _normalize_url(original)
        
        # Should be in alphabetical order
        assert result == "https://example.com?a=first&m=middle&z=last"
    
    def test_normalize_url_mixed_tracking_and_essential(self):
        """Test mixed tracking and essential parameters"""
        original = "https://example.com?id=123&utm_source=google&page=2&ref=twitter&sort=date"
        expected = "https://example.com?id=123&page=2&sort=date"
        result = _normalize_url(original)
        assert result == expected


class TestTypeConversions:
    """Test type conversion helper functions"""
    
    def test_datetime_to_iso_format_utc_aware(self):
        """Test UTC-aware datetime conversion to ISO format"""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45Z"
        assert result == expected
    
    def test_datetime_to_iso_format_naive(self):
        """Test naive datetime conversion to ISO format (treated as UTC)"""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45Z"  # Z suffix added (naive treated as UTC)
        assert result == expected
    
    def test_datetime_to_iso_strips_microseconds(self):
        """Test microseconds are stripped from datetime"""
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45Z"  # Microseconds stripped
        assert result == expected
    
    def test_decimal_to_text_precision_preservation(self):
        """Test Decimal to TEXT preserves exact precision"""
        test_cases = [
            (Decimal('123.45'), '123.45'),
            (Decimal('0.000001'), '0.000001'),
            (Decimal('999999.999999'), '999999.999999'),
            (Decimal('10.0'), '10.0'),  # Trailing zero preserved
            (Decimal('0'), '0'),
        ]
        
        for decimal_val, expected in test_cases:
            result = _decimal_to_text(decimal_val)
            assert result == expected, f"Failed for {decimal_val}: expected {expected}, got {result}"


class TestNewsItemStorage:
    """Test news item storage operations"""
    
    def test_store_news_deduplication_insert_or_ignore(self, temp_db):
        """Test news storage with URL normalization and deduplication"""
        # Create test news items with different URLs that normalize to same
        items = [
            NewsItem(
                symbol="AAPL",
                url="https://example.com/news/1?utm_source=google",
                headline="Apple News",
                source="Reuters",
                published=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
            ),
            NewsItem(
                symbol="AAPL", 
                url="https://example.com/news/1?ref=twitter",  # Same normalized URL
                headline="Apple News Updated",  # Different headline
                source="Reuters",
                published=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
            )
        ]
        
        # Store news items - second item should be ignored due to URL normalization
        store_news_items(temp_db, items)
        
        # Verify deduplication worked - only first item should remain
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*), headline, url FROM news_items 
                WHERE symbol = 'AAPL'
            """)
            count, headline, stored_url = cursor.fetchone()
            
            assert count == 1, f"Expected 1 record, got {count}"
            assert headline == "Apple News", "First record should be kept"
            assert stored_url == "https://example.com/news/1", "URL should be normalized"
    
    def test_store_news_empty_list_no_error(self, temp_db):
        """Test storing empty news list doesn't cause errors"""
        store_news_items(temp_db, [])  # Should not raise error
        
        # Verify no records stored
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM news_items")
            count = cursor.fetchone()[0]
            assert count == 0


class TestPriceDataStorage:
    """Test price data storage operations"""
    
    def test_store_price_data_type_conversions(self, temp_db):
        """Test price data storage with Decimal and enum conversions"""
        # Create test price data
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
                price=Decimal('150.25'),
                volume=1000000,
                session=Session.REG
            )
        ]
        
        # Store price data
        store_price_data(temp_db, items)
        
        # Verify data stored with proper conversions
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, timestamp_iso, price, volume, session 
                FROM price_data WHERE symbol = 'AAPL'
            """)
            row = cursor.fetchone()
            
            assert row[0] == "AAPL"
            assert row[1] == "2024-01-15T09:30:00Z"  # ISO format
            assert row[2] == "150.25"  # Decimal as TEXT
            assert row[3] == 1000000  # Integer volume
            assert row[4] == "REG"  # Enum as string value
    
    def test_store_price_data_deduplication(self, temp_db):
        """Test price data deduplication on (symbol, timestamp) key"""
        # Create duplicate price data (same symbol, timestamp)
        timestamp = datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc)
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=timestamp,
                price=Decimal('150.00'),
                volume=1000000,
                session=Session.REG
            ),
            PriceData(
                symbol="AAPL",
                timestamp=timestamp,  # Same timestamp
                price=Decimal('151.00'),  # Different price
                volume=2000000,
                session=Session.PRE
            )
        ]
        
        # Store price data - second item should be ignored (same symbol+timestamp)
        store_price_data(temp_db, items)
        
        # Verify deduplication worked - first item wins with INSERT OR IGNORE
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*), price FROM price_data 
                WHERE symbol = 'AAPL' AND timestamp_iso = '2024-01-15T09:30:00Z'
            """)
            count, price = cursor.fetchone()
            
            assert count == 1, f"Expected 1 record, got {count}"
            assert price == "150.00", "First record should be kept"


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


class TestHoldingsUpsert:
    """Test holdings upsert operations"""
    
    def test_upsert_holdings_timestamp_handling(self, temp_db):
        """Test holdings upsert preserves created_at, updates updated_at"""
            
            # Initial holdings
        holdings1 = Holdings(
            symbol="AAPL",
            quantity=Decimal('100'),
            break_even_price=Decimal('150.00'),
            total_cost=Decimal('15000.00'),
            notes="Initial position",
            created_at=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
        )
        
        # Store initial holdings
        upsert_holdings(temp_db, holdings1)
            
        # Updated holdings (same symbol = conflict)
        holdings2 = Holdings(
            symbol="AAPL",  # Same primary key
            quantity=Decimal('150'),  # Should update
            break_even_price=Decimal('148.00'),  # Should update
            total_cost=Decimal('22200.00'),  # Should update
            notes="Added more shares",  # Should update
            created_at=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),  # Should be ignored (preserve original)
            updated_at=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)   # Should update
        )
        
        # Upsert updated holdings
        upsert_holdings(temp_db, holdings2)
        
        # Verify record was updated properly
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*), quantity, break_even_price, total_cost, notes,
                        created_at_iso, updated_at_iso
                FROM holdings WHERE symbol = 'AAPL'
            """)
            count, qty, price, cost, notes, created, updated = cursor.fetchone()
            
            assert count == 1, f"Expected 1 record, got {count}"
            assert qty == "150", "quantity should be updated"
            assert price == "148.00", "break_even_price should be updated"
            assert cost == "22200.00", "total_cost should be updated"
            assert notes == "Added more shares", "notes should be updated"
            assert created == "2024-01-15T09:00:00Z", "created_at should be preserved from first insert"
            assert updated == "2024-01-15T12:00:00Z", "updated_at should be from update"
    
    def test_upsert_holdings_auto_timestamps(self, temp_db):
        """Test automatic timestamp generation when not provided"""
            
        # Holdings without timestamps
        holdings = Holdings(
            symbol="TSLA",
            quantity=Decimal('50'),
            break_even_price=Decimal('200.00'),
            total_cost=Decimal('10000.00'),
            notes="New position"
            # created_at and updated_at not provided
        )
        
        # Store holdings
        upsert_holdings(temp_db, holdings)
        
        # Verify timestamps were set automatically
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT created_at_iso, updated_at_iso FROM holdings 
                WHERE symbol = 'TSLA'
            """)
            created, updated = cursor.fetchone()
            
            # Both should be valid ISO timestamps
            assert created is not None
            assert updated is not None  
            assert "T" in created and "T" in updated
            assert created.endswith("Z") and updated.endswith("Z")
            # Should be approximately the same time
            assert created == updated


class TestQueryOperations:
    """Test data query operations"""
    
    def test_get_news_since_timestamp_filtering(self, temp_db):
        """Test news retrieval with timestamp filtering"""
        # Store news items with different timestamps
        items = [
            NewsItem(
                symbol="AAPL",
                url="https://example.com/1",
                headline="Old News",
                source="Reuters",
                published=datetime(2024, 1, 10, 10, 0, tzinfo=timezone.utc)
            ),
            NewsItem(
                symbol="AAPL", 
                url="https://example.com/2",
                headline="Recent News",
                source="Reuters",
                published=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
            ),
            NewsItem(
                symbol="TSLA",
                url="https://example.com/3", 
                headline="Tesla News",
                source="Reuters",
                published=datetime(2024, 1, 20, 10, 0, tzinfo=timezone.utc)
            )
        ]
        
        store_news_items(temp_db, items)
        
        # Query news since 2024-01-12 (should get 2 items)
        since = datetime(2024, 1, 12, 0, 0, tzinfo=timezone.utc)
        results = get_news_since(temp_db, since)
        
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Verify results are ordered by published time
        assert results[0].headline == "Recent News"
        assert results[1].headline == "Tesla News"
        
        # Verify all expected fields are present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'url')
            assert hasattr(result, 'headline')
            assert hasattr(result, 'content')
            assert hasattr(result, 'published')
            assert hasattr(result, 'source')
    
    def test_get_price_data_since_ordering(self, temp_db):
        """Test price data retrieval with proper ordering"""
        # Store price data in random order
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                price=Decimal('150.00'),
                session=Session.REG
            ),
            PriceData(
                symbol="AAPL", 
                timestamp=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc), 
                price=Decimal('149.00'),
                session=Session.PRE
            ),
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
                price=Decimal('151.00'), 
                session=Session.POST
            )
        ]
        
        store_price_data(temp_db, items)
        
        # Query all price data
        since = datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)
        results = get_price_data_since(temp_db, since)
        
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        
        # Verify chronological ordering
        assert results[0].timestamp == datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
        assert results[1].timestamp == datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert results[2].timestamp == datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)
        
        # Verify all fields present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'timestamp')
            assert hasattr(result, 'price')
            assert hasattr(result, 'volume')
            assert hasattr(result, 'session')
    
    def test_get_all_holdings_ordering(self, temp_db):
        """Test holdings retrieval with symbol ordering"""
        # Store holdings in random symbol order
        holdings_list = [
            Holdings(
                symbol="TSLA",
                quantity=Decimal('50'),
                break_even_price=Decimal('200.00'),
                total_cost=Decimal('10000.00')
            ),
            Holdings(
                symbol="AAPL", 
                quantity=Decimal('100'),
                break_even_price=Decimal('150.00'),
                total_cost=Decimal('15000.00')
            ),
            Holdings(
                symbol="MSFT",
                quantity=Decimal('75'),
                break_even_price=Decimal('300.00'), 
                total_cost=Decimal('22500.00')
            )
        ]
        
        for holdings in holdings_list:
            upsert_holdings(temp_db, holdings)
        
        # Query all holdings
        results = get_all_holdings(temp_db)
        
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        
        # Verify alphabetical symbol ordering
        symbols = [result.symbol for result in results]
        assert symbols == ['AAPL', 'MSFT', 'TSLA'], f"Expected alphabetical order, got {symbols}"
        
        # Verify all fields present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'quantity')
            assert hasattr(result, 'break_even_price')
            assert hasattr(result, 'total_cost')
            assert hasattr(result, 'notes')
            assert hasattr(result, 'created_at')
            assert hasattr(result, 'updated_at')
    
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
                last_updated=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                result_json='{"sentiment": "positive"}'
            ),
            AnalysisResult(
                symbol="AAPL",
                analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
                model_name="claude-3",
                stance=Stance.NEUTRAL,
                confidence_score=0.75,
                last_updated=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
                result_json='{"sentiment": "neutral"}'
            ),
            AnalysisResult(
                symbol="TSLA", 
                analysis_type=AnalysisType.NEWS_ANALYSIS,
                model_name="gpt-4",
                stance=Stance.BEAR,
                confidence_score=0.90,
                last_updated=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
                result_json='{"sentiment": "bearish"}'
            )
        ]
        
        for result in results:
            upsert_analysis_result(temp_db, result)
        
        # Test filtering by symbol
        aapl_results = get_analysis_results(temp_db, symbol="AAPL")
        assert len(aapl_results) == 2, f"Expected 2 AAPL results, got {len(aapl_results)}"
        
        # Verify correct symbol filtering
        for result in aapl_results:
            assert result.symbol == "AAPL"
        
        # Test getting all results (no filter)
        all_results = get_analysis_results(temp_db)
        assert len(all_results) == 3, f"Expected 3 total results, got {len(all_results)}"
        
        # Verify ordering (symbol ASC, analysis_type ASC)
        symbols_and_types = [(r.symbol, r.analysis_type.value) for r in all_results]
        expected = [('AAPL', 'news_analysis'), ('AAPL', 'sentiment_analysis'), ('TSLA', 'news_analysis')]
        assert symbols_and_types == expected, f"Expected {expected}, got {symbols_and_types}"
    
    def test_get_news_before_cutoff_filtering(self, temp_db):
        """Test news retrieval with created_at cutoff filtering for LLM batch processing"""
        import time
        
        # Create news items with different created_at times
        # We need to insert them with delays to ensure different created_at_iso values
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # First item - oldest
        item1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/old",
            headline="Old News",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [item1])
        time.sleep(1)  # 1 second delay to ensure different created_at
        
        # Second item - middle
        item2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/middle",
            headline="Middle News",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [item2])
        
        # Record cutoff time right after second item
        cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay before third item
        
        # Third item - newest
        item3 = NewsItem(
            symbol="AAPL",
            url="https://example.com/new",
            headline="New News",
            source="Yahoo",
            published=base_time
        )
        store_news_items(temp_db, [item3])
        
        # Query news before cutoff (should get first 2 items)
        results = get_news_before(temp_db, cutoff)
        
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Verify ordering by created_at ASC, then symbol ASC
        assert results[0].headline == "Old News"
        assert results[1].headline == "Middle News"
        
        # Verify all expected fields are present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'url')
            assert hasattr(result, 'headline')
            assert hasattr(result, 'content')
            assert hasattr(result, 'published')
            assert hasattr(result, 'source')
    
    def test_get_news_before_boundary_conditions(self, temp_db):
        """Test get_news_before with boundary conditions using spaced items"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Store first news item
        item1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/item1",
            headline="First News",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [item1])
        time.sleep(1)  # 1 second delay
        
        # Record time between items
        between_cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay
        
        # Store second news item
        item2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/item2",
            headline="Second News",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [item2])
        
        # Test 1: Cutoff before all items (should get nothing)
        past_cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = get_news_before(temp_db, past_cutoff)
        assert len(results) == 0, f"Expected 0 results for past cutoff, got {len(results)}"
        
        # Test 2: Cutoff between items (should get first item only)
        results = get_news_before(temp_db, between_cutoff)
        assert len(results) == 1, f"Expected 1 result for between cutoff, got {len(results)}"
        assert results[0].headline == "First News"
        
        # Test 3: Cutoff well after all items (should get both)
        future_cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)
        results = get_news_before(temp_db, future_cutoff)
        assert len(results) == 2, f"Expected 2 results for future cutoff, got {len(results)}"
        
        # Test 4: Exact timestamp match with current time (should get both items)
        exact_cutoff = datetime.now(timezone.utc)
        results = get_news_before(temp_db, exact_cutoff)
        assert len(results) == 2, f"Expected 2 results for exact match, got {len(results)}"
    
    def test_get_prices_before_cutoff_filtering(self, temp_db):
        """Test price data retrieval with created_at cutoff filtering for LLM batch processing"""
        import time
        
        # Create price data with different created_at times
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # First price - oldest
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal('150.00'),
            session=Session.REG
        )
        store_price_data(temp_db, [price1])
        time.sleep(1)  # 1 second delay
        
        # Second price - middle
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time + timedelta(hours=1),
            price=Decimal('200.00'),
            session=Session.PRE
        )
        store_price_data(temp_db, [price2])
        
        # Record cutoff time right after second item
        cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay before third item
        
        # Third price - newest
        price3 = PriceData(
            symbol="AAPL",
            timestamp=base_time + timedelta(hours=2),
            price=Decimal('151.00'),
            session=Session.POST
        )
        store_price_data(temp_db, [price3])
        
        # Query prices before cutoff (should get first 2 items)
        results = get_prices_before(temp_db, cutoff)
        
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Verify ordering by created_at ASC, then symbol ASC
        assert results[0].price == Decimal('150.00')
        assert results[1].price == Decimal('200.00')
        
        # Verify all expected fields are present
        for result in results:
            assert hasattr(result, 'symbol')
            assert hasattr(result, 'timestamp')
            assert hasattr(result, 'price')
            assert hasattr(result, 'volume')
            assert hasattr(result, 'session')
    
    def test_get_prices_before_boundary_conditions(self, temp_db):
        """Test get_prices_before with boundary conditions using spaced items"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Store first price data point
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal('150.00'),
            volume=1000000,
            session=Session.REG
        )
        store_price_data(temp_db, [price1])
        time.sleep(1)  # 1 second delay
        
        # Record time between items
        between_cutoff = datetime.now(timezone.utc)
        time.sleep(1)  # 1 second delay
        
        # Store second price data point
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time + timedelta(hours=1),
            price=Decimal('200.00'),
            volume=2000000,
            session=Session.PRE
        )
        store_price_data(temp_db, [price2])
        
        # Test 1: Cutoff before all items (should get nothing)
        past_cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = get_prices_before(temp_db, past_cutoff)
        assert len(results) == 0, f"Expected 0 results for past cutoff, got {len(results)}"
        
        # Test 2: Cutoff between items (should get first item only)
        results = get_prices_before(temp_db, between_cutoff)
        assert len(results) == 1, f"Expected 1 result for between cutoff, got {len(results)}"
        assert results[0].price == Decimal('150.00')
        assert results[0].symbol == "AAPL"
        
        # Test 3: Cutoff well after all items (should get both)
        future_cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)
        results = get_prices_before(temp_db, future_cutoff)
        assert len(results) == 2, f"Expected 2 results for future cutoff, got {len(results)}"
        
        # Test 4: Exact timestamp match with current time (should get both items)
        exact_cutoff = datetime.now(timezone.utc)
        results = get_prices_before(temp_db, exact_cutoff)
        assert len(results) == 2, f"Expected 2 results for exact match, got {len(results)}"


class TestErrorHandling:
    """Test comprehensive error handling and edge cases"""
    
    def test_database_operations_with_nonexistent_db(self):
        """Test operations fail gracefully with non-existent database"""
        nonexistent_path = "/nonexistent/path/database.db"
        
        # Create test data to force actual database connection attempt
        test_item = NewsItem(
            symbol="AAPL",
            url="https://example.com/test",
            headline="Test News",
            source="Test",
            published=datetime.now(timezone.utc)
        )
        
        # Operations should raise appropriate database errors
        with pytest.raises((sqlite3.OperationalError, FileNotFoundError)):
            store_news_items(nonexistent_path, [test_item])  # Forces DB connection
            
        with pytest.raises((sqlite3.OperationalError, FileNotFoundError)):
            get_news_since(nonexistent_path, datetime.now(timezone.utc))
    
    def test_query_operations_with_empty_database(self, temp_db):
        """Test query operations return empty results with empty database"""
        # All query operations should return empty lists
        now = datetime.now(timezone.utc)
        assert get_news_since(temp_db, now) == []
        assert get_price_data_since(temp_db, now) == []
        assert get_news_before(temp_db, now) == []
        assert get_prices_before(temp_db, now) == []
        assert get_all_holdings(temp_db) == []
        assert get_analysis_results(temp_db) == []
        assert get_analysis_results(temp_db, symbol="NONEXISTENT") == []


class TestLastSeenState:
    """Test last_seen table key-value storage operations"""
    
    def test_basic_roundtrip_set_get(self, temp_db):
        """Test basic set/get functionality"""
        # Set a key-value pair using allowed key
        set_last_seen(temp_db, 'news_since_iso', '2024-01-15T10:30:00Z')
        
        # Retrieve it
        result = get_last_seen(temp_db, 'news_since_iso')
        assert result == '2024-01-15T10:30:00Z'
    
    def test_replace_existing_key(self, temp_db):
        """Test INSERT OR REPLACE behavior - overwriting existing keys"""
        # Set initial value
        set_last_seen(temp_db, 'llm_last_run_iso', '2024-01-15T09:00:00Z')
        assert get_last_seen(temp_db, 'llm_last_run_iso') == '2024-01-15T09:00:00Z'
        
        # Overwrite with new value
        set_last_seen(temp_db, 'llm_last_run_iso', '2024-01-15T10:00:00Z')
        
        # Should return the new value only
        result = get_last_seen(temp_db, 'llm_last_run_iso')
        assert result == '2024-01-15T10:00:00Z'
        
        # Verify only one record exists
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM last_seen WHERE key = 'llm_last_run_iso'")
            count = cursor.fetchone()[0]
            assert count == 1, "Should have exactly one record after replacement"
    
    def test_unknown_key_returns_none(self, temp_db):
        """Test that non-existent keys return None"""
        # Test with allowed key that hasn't been set
        result = get_last_seen(temp_db, 'news_since_iso')
        assert result is None
    
    def test_unicode_safety(self, temp_db):
        """Test unicode handling in values and key constraint enforcement"""
        # Test unicode value with allowed key
        unicode_value = 'résumé📈'
        set_last_seen(temp_db, 'news_since_iso', unicode_value)
        result = get_last_seen(temp_db, 'news_since_iso')
        assert result == unicode_value
        
        # Test both allowed keys work
        set_last_seen(temp_db, 'llm_last_run_iso', '2024-01-15T10:30:00Z')
        result = get_last_seen(temp_db, 'llm_last_run_iso')
        assert result == '2024-01-15T10:30:00Z'
    
    def test_key_constraint_enforcement(self, temp_db):
        """Test that CHECK constraint rejects invalid keys"""
        # Should raise constraint error for invalid key
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            set_last_seen(temp_db, 'invalid_key', 'some_value')


class TestLastNewsTime:
    """Test specialized last news time tracking functions"""
    
    def test_roundtrip_aware_timestamp(self, temp_db):
        """Test UTC-aware datetime roundtrip"""
        # Set a UTC-aware timestamp
        dt_aware = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        set_last_news_time(temp_db, dt_aware)
        
        # Retrieve it
        result = get_last_news_time(temp_db)
        
        # Should be equal when both are UTC-aware
        assert result == dt_aware
        assert result.tzinfo == timezone.utc
        
        # Check underlying storage format
        raw_value = get_last_seen(temp_db, 'news_since_iso')
        assert raw_value == "2024-01-15T10:30:45Z"
    
    def test_naive_timestamp_treated_as_utc(self, temp_db):
        """Test naive datetime is treated as UTC"""
        # Set naive timestamp
        dt_naive = datetime(2024, 1, 15, 10, 30, 45)
        set_last_news_time(temp_db, dt_naive)
        
        # Retrieve it - should be UTC-aware
        result = get_last_news_time(temp_db)
        expected = dt_naive.replace(tzinfo=timezone.utc)
        
        assert result == expected
        assert result.tzinfo == timezone.utc
        
        # Check underlying storage format
        raw_value = get_last_seen(temp_db, 'news_since_iso')
        assert raw_value == "2024-01-15T10:30:45Z"
    
    def test_overwrite_behavior(self, temp_db):
        """Test last write wins - no monotonic enforcement"""
        # Set older time first
        older_time = datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
        set_last_news_time(temp_db, older_time)
        assert get_last_news_time(temp_db) == older_time
        
        # Set newer time
        newer_time = datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)
        set_last_news_time(temp_db, newer_time)
        assert get_last_news_time(temp_db) == newer_time
        
        # Set even older time - should still work (last write wins)
        much_older_time = datetime(2024, 1, 14, 8, 0, tzinfo=timezone.utc)
        set_last_news_time(temp_db, much_older_time)
        assert get_last_news_time(temp_db) == much_older_time
    
    def test_missing_key_returns_none(self, temp_db):
        """Test None returned when news_since_iso key doesn't exist"""
        # Don't set anything
        result = get_last_news_time(temp_db)
        assert result is None


class TestBatchOperations:
    """Test batch operations like commit_llm_batch and finalize_database"""
    
    def test_commit_llm_batch_atomic_transaction(self, temp_db):
        """Test commit_llm_batch performs atomic transaction with correct deletions"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Insert news items with different created_at times
        news1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="News 1",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [news1])
        time.sleep(1)
        
        news2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/news2",
            headline="News 2",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [news2])
        
        # Record cutoff between items 2 and 3
        cutoff = datetime.now(timezone.utc)
        time.sleep(1)
        
        news3 = NewsItem(
            symbol="GOOGL",
            url="https://example.com/news3",
            headline="News 3",
            source="Yahoo",
            published=base_time
        )
        store_news_items(temp_db, [news3])
        
        # Also insert price data with similar timing
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal('150.00'),
            session=Session.REG
        )
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time,
            price=Decimal('200.00'),
            session=Session.PRE
        )
        price3 = PriceData(
            symbol="GOOGL",
            timestamp=base_time,
            price=Decimal('100.00'),
            session=Session.POST
        )
        
        # Store price data (using existing created_at from news for simplicity)
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            # Insert prices with specific created_at times matching news items
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, session, created_at_iso)
                SELECT ?, ?, ?, ?, created_at_iso
                FROM news_items WHERE symbol = ?
            """, ("AAPL", _datetime_to_iso(base_time), str(price1.price), "REG", "AAPL"))
            
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, session, created_at_iso)
                SELECT ?, ?, ?, ?, created_at_iso
                FROM news_items WHERE symbol = ?
            """, ("TSLA", _datetime_to_iso(base_time), str(price2.price), "PRE", "TSLA"))
            
            cursor.execute("""
                INSERT INTO price_data (symbol, timestamp_iso, price, session, created_at_iso)
                SELECT ?, ?, ?, ?, created_at_iso
                FROM news_items WHERE symbol = ?
            """, ("GOOGL", _datetime_to_iso(base_time), str(price3.price), "POST", "GOOGL"))
            conn.commit()
        
        # Execute commit_llm_batch
        result = commit_llm_batch(temp_db, cutoff)
        
        # Verify return value
        assert result["news_deleted"] == 2, f"Expected 2 news deleted, got {result['news_deleted']}"
        assert result["prices_deleted"] == 2, f"Expected 2 prices deleted, got {result['prices_deleted']}"
        
        # Verify remaining data
        remaining_news = get_news_since(temp_db, datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert len(remaining_news) == 1, f"Expected 1 news item remaining, got {len(remaining_news)}"
        assert remaining_news[0].headline == "News 3"
        
        remaining_prices = get_price_data_since(temp_db, datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert len(remaining_prices) == 1, f"Expected 1 price remaining, got {len(remaining_prices)}"
        assert remaining_prices[0].symbol == "GOOGL"
        
        # Verify last_seen watermark was set
        assert get_last_seen(temp_db, 'llm_last_run_iso') == _datetime_to_iso(cutoff)
    
    def test_commit_llm_batch_empty_database(self, temp_db):
        """Test commit_llm_batch on empty database"""
        cutoff = datetime.now(timezone.utc)
        
        # Execute on empty database
        result = commit_llm_batch(temp_db, cutoff)
        
        # Should delete nothing
        assert result["news_deleted"] == 0
        assert result["prices_deleted"] == 0
        
        # Should still set the watermark
        assert get_last_seen(temp_db, 'llm_last_run_iso') == _datetime_to_iso(cutoff)
    
    def test_commit_llm_batch_boundary_conditions(self, temp_db):
        """Test commit_llm_batch with exact timestamp boundary"""
        import time
        
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Insert two items
        news1 = NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="News 1",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [news1])
        time.sleep(1)
        
        # Get exact timestamp of second item
        news2 = NewsItem(
            symbol="TSLA",
            url="https://example.com/news2",
            headline="News 2",
            source="Bloomberg",
            published=base_time
        )
        store_news_items(temp_db, [news2])
        
        # Get the exact created_at of the second item
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at_iso FROM news_items WHERE symbol = 'TSLA'")
            exact_timestamp_iso = cursor.fetchone()[0]
        
        exact_cutoff = datetime.fromisoformat(exact_timestamp_iso.replace('Z', '+00:00'))
        
        # Commit with exact timestamp (should delete both due to <=)
        result = commit_llm_batch(temp_db, exact_cutoff)
        
        assert result["news_deleted"] == 2, f"Expected 2 deleted with <= boundary, got {result['news_deleted']}"
        
        # Verify all deleted
        remaining = get_news_since(temp_db, datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert len(remaining) == 0, f"Expected 0 items remaining, got {len(remaining)}"
    
    def test_commit_llm_batch_idempotency(self, temp_db):
        """Test commit_llm_batch can be called multiple times with same cutoff"""
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        
        # Insert test data
        news = NewsItem(
            symbol="AAPL",
            url="https://example.com/news",
            headline="Test News",
            source="Reuters",
            published=base_time
        )
        store_news_items(temp_db, [news])
        
        cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)
        
        # First call should delete the item
        result1 = commit_llm_batch(temp_db, cutoff)
        assert result1["news_deleted"] == 1
        
        # Second call with same cutoff should delete nothing
        result2 = commit_llm_batch(temp_db, cutoff)
        assert result2["news_deleted"] == 0
        assert result2["prices_deleted"] == 0
        
        # Watermark should still be updated
        assert get_last_seen(temp_db, 'llm_last_run_iso') == _datetime_to_iso(cutoff)
