"""
Storage operations tests.
Tests CRUD operations, type conversions, and SQLite database functionality.
Uses Windows-safe cleanup patterns for WAL mode databases.
"""

import sys
from pathlib import Path
import pytest
import sqlite3
import tempfile
import os
import gc
from datetime import datetime, timezone
from decimal import Decimal

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))
# Add tests directory to path to import conftest
sys.path.append(str(Path(__file__).parent))

from data.storage import (
    init_database, store_news_items, store_price_data,
    get_news_since, get_price_data_since, upsert_analysis_result,
    upsert_holdings, get_all_holdings, get_analysis_results,
    _normalize_url, _datetime_to_iso, _decimal_to_text
)
from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)
from conftest import cleanup_sqlite_artifacts



@pytest.fixture
def temp_db_path():
    """Provides temporary database file path with automatic cleanup"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield db_path
    cleanup_sqlite_artifacts(db_path)


@pytest.fixture
def temp_db():
    """Provides initialized temporary database with automatic cleanup"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_database(db_path)
    yield db_path
    cleanup_sqlite_artifacts(db_path)


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
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['analysis_results', 'holdings', 'news_items', 'price_data']
            assert tables == expected_tables, f"Expected {expected_tables}, got {tables}"
    
    def test_schema_file_not_found_raises_error(self):
        """Test FileNotFoundError when schema.sql is missing"""
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp_file:
            # Temporarily move schema.sql to cause FileNotFoundError
            schema_path = Path(__file__).parent.parent / 'data' / 'schema.sql'
            backup_path = schema_path.with_suffix('.sql.backup')
            
            if schema_path.exists():
                schema_path.rename(backup_path)
                
                try:
                    with pytest.raises(FileNotFoundError, match="Schema file not found"):
                        init_database(tmp_file.name)
                finally:
                    # Restore schema.sql
                    backup_path.rename(schema_path)
    
    def test_wal_mode_enabled(self, temp_db_path):
        """Test WAL mode is properly enabled (requires file-backed DB)"""
        # Initialize database
        init_database(temp_db_path)
        
        # Check WAL mode is enabled
        with sqlite3.connect(temp_db_path) as conn:
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
             "https://example.com"),
             
            # Case insensitive removal
            ("https://example.com?UTM_Source=google&CAMPAIGN=test", 
             "https://example.com"),
            ("https://example.com?REF=twitter&Source=email", 
             "https://example.com"),
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
        """Test naive datetime conversion to ISO format"""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = _datetime_to_iso(dt)
        expected = "2024-01-15T10:30:45"  # No Z suffix for naive
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
        assert results[0]['headline'] == "Recent News"
        assert results[1]['headline'] == "Tesla News"
        
        # Verify all expected fields are present
        for result in results:
            assert 'symbol' in result
            assert 'url' in result
            assert 'headline' in result
            assert 'content' in result
            assert 'published_iso' in result
            assert 'source' in result
            assert 'created_at_iso' in result
    
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
        assert results[0]['timestamp_iso'] == "2024-01-15T09:00:00Z"
        assert results[1]['timestamp_iso'] == "2024-01-15T10:00:00Z"
        assert results[2]['timestamp_iso'] == "2024-01-15T11:00:00Z"
        
        # Verify all fields present
        for result in results:
            assert 'symbol' in result
            assert 'timestamp_iso' in result
            assert 'price' in result
            assert 'volume' in result
            assert 'session' in result
            assert 'created_at_iso' in result
    
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
        symbols = [result['symbol'] for result in results]
        assert symbols == ['AAPL', 'MSFT', 'TSLA'], f"Expected alphabetical order, got {symbols}"
        
        # Verify all fields present
        for result in results:
            assert 'symbol' in result
            assert 'quantity' in result
            assert 'break_even_price' in result
            assert 'total_cost' in result
            assert 'notes' in result
            assert 'created_at_iso' in result
            assert 'updated_at_iso' in result
    
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
            assert result['symbol'] == "AAPL"
        
        # Test getting all results (no filter)
        all_results = get_analysis_results(temp_db)
        assert len(all_results) == 3, f"Expected 3 total results, got {len(all_results)}"
        
        # Verify ordering (symbol ASC, analysis_type ASC)
        symbols_and_types = [(r['symbol'], r['analysis_type']) for r in all_results]
        expected = [('AAPL', 'news_analysis'), ('AAPL', 'sentiment_analysis'), ('TSLA', 'news_analysis')]
        assert symbols_and_types == expected, f"Expected {expected}, got {symbols_and_types}"


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
        assert get_news_since(temp_db, datetime.now(timezone.utc)) == []
        assert get_price_data_since(temp_db, datetime.now(timezone.utc)) == []
        assert get_all_holdings(temp_db) == []
        assert get_analysis_results(temp_db) == []
        assert get_analysis_results(temp_db, symbol="NONEXISTENT") == []


if __name__ == "__main__":
    pytest.main([__file__])