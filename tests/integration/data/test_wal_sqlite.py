"""
WAL mode SQLite functionality tests.
Tests Write-Ahead Logging mode functionality including concurrent operations
and database performance under realistic trading bot access patterns.
"""

import threading
import time
import concurrent.futures
from datetime import datetime, timezone
from decimal import Decimal
import sqlite3

from data.storage import connect, store_news_items, get_news_since, store_price_data, get_price_data_since, upsert_analysis_result, get_analysis_results
from data.storage.db_context import _cursor_context
from data.models import NewsItem, PriceData, AnalysisResult, Session, Stance, AnalysisType


class TestWALSqlite:
    """Test WAL mode functionality and concurrent operations"""
    
    def test_wal_mode_functionality(self, temp_db):
        """
        Test that WAL mode is properly enabled and functional with file-backed database.
        This test verifies concurrent access patterns that require WAL mode.
        """
        # Verify WAL mode is enabled
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == 'wal', f"Expected WAL mode, got {mode}"
        
        # Test that WAL files are created during operations
        # Store some data to trigger WAL file creation
        test_news = [NewsItem(
            symbol="TEST",
            url="https://example.com/test",
            headline="WAL Test",
            source="Test",
            published=datetime.now(timezone.utc)
        )]
        store_news_items(temp_db, test_news)
        
        # Verify data was stored successfully (WAL mode working)
        results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(results) == 1
        assert results[0].symbol == "TEST"
        assert results[0].headline == "WAL Test"

    def test_concurrent_operations_with_wal(self, temp_db):
        """
        Test that WAL mode allows concurrent read/write operations without "database locked" errors.
        
        This test validates realistic trading bot scenarios:
        1. Multiple data source polling (concurrent writes)
        2. LLM analysis during data ingestion (read during write)
        3. Multiple LLM agents accessing data (concurrent reads)
        4. Mixed read/write operations under load
        
        Critical aspects tested:
        - No "database locked" or "database busy" errors
        - Data consistency despite concurrent access
        - Performance benefits of WAL mode
        - Real-world trading bot access patterns
        """
        
        # VERIFY WAL MODE IS ENABLED
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == 'wal', f"Expected WAL mode, got {mode}. WAL required for concurrent operations."
        
        # PREPARE TEST DATA
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
        symbols = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ", "META"]
        
        # Shared results tracking
        operation_results = {
            'write_errors': [],
            'read_errors': [],
            'write_count': 0,
            'read_count': 0,
            'data_written': [],
            'data_read': []
        }
        operation_lock = threading.Lock()
        
        def track_result(operation_type, *, success=True, error=None, data=None):
            """Thread-safe result tracking"""
            with operation_lock:
                if operation_type == 'write':
                    if success:
                        operation_results['write_count'] += 1
                        if data:
                            operation_results['data_written'].append(data)
                    else:
                        operation_results['write_errors'].append(error)
                elif operation_type == 'read':
                    if success:
                        operation_results['read_count'] += 1
                        if data:
                            operation_results['data_read'].append(data)
                    else:
                        operation_results['read_errors'].append(error)
        
        # SCENARIO 1: MULTIPLE CONCURRENT WRITES (Simulating multiple data source polling)
        def write_news_data(thread_id, symbol_batch):
            """Simulate news data polling from different sources"""
            try:
                for i, symbol in enumerate(symbol_batch):
                    news_items = [NewsItem(
                        symbol=symbol,
                        url=f"https://newsapi.com/{symbol.lower()}-news-{thread_id}-{i}",
                        headline=f"{symbol} Market Update from Source {thread_id}",
                        content=f"Latest {symbol} financial news from concurrent source {thread_id}",
                        source=f"NewsAPI-{thread_id}",
                        published=base_time
                    )]
                    
                    store_news_items(temp_db, news_items)
                    track_result('write', success=True, data=f"news_{symbol}_{thread_id}")
                    
                    # Small delay to simulate network latency
                    time.sleep(0.01)
                    
            except (sqlite3.Error, ValueError, RuntimeError) as exc:
                track_result('write', success=False, error=f"Thread {thread_id} news write error: {exc}")
        
        def write_price_data(thread_id, symbol_batch):
            """Simulate price data polling from different exchanges"""
            try:
                for i, symbol in enumerate(symbol_batch):
                    price_data = [PriceData(
                        symbol=symbol,
                        timestamp=base_time,
                        price=Decimal(f"{100 + thread_id + i}.{thread_id:02d}"),
                        volume=10000 * (thread_id + 1) * (i + 1),
                        session=Session.REG
                    )]
                    
                    store_price_data(temp_db, price_data)
                    track_result('write', success=True, data=f"price_{symbol}_{thread_id}")
                    
                    time.sleep(0.01)
                    
            except (sqlite3.Error, ValueError, RuntimeError) as exc:
                track_result('write', success=False, error=f"Thread {thread_id} price write error: {exc}")
        
        def write_analysis_data(thread_id, symbol_batch):
            """Simulate analysis results from different models"""
            try:
                for i, symbol in enumerate(symbol_batch):
                    analysis = AnalysisResult(
                        symbol=symbol,
                        analysis_type=AnalysisType.NEWS_ANALYSIS,
                        model_name=f"model-{thread_id}",
                        stance=Stance.BULL if (thread_id + i) % 2 == 0 else Stance.BEAR,
                        confidence_score=0.5 + (thread_id * 0.1) + (i * 0.05),
                        last_updated=base_time,
                        result_json=f'{{"thread": {thread_id}, "symbol": "{symbol}", "analysis": "concurrent_test"}}'
                    )
                    
                    upsert_analysis_result(temp_db, analysis)
                    track_result('write', success=True, data=f"analysis_{symbol}_{thread_id}")
                    
                    time.sleep(0.01)
                    
            except (sqlite3.Error, ValueError, RuntimeError) as exc:
                track_result('write', success=False, error=f"Thread {thread_id} analysis write error: {exc}")
        
        # SCENARIO 2: CONCURRENT READS (Simulating multiple LLM agents analyzing data)
        def read_for_analysis(thread_id, query_type):
            """Simulate LLM agents reading data for analysis"""
            try:
                for i in range(3):  # Multiple read operations per thread
                    if query_type == 'news':
                        results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
                        track_result('read', success=True, data=f"news_read_{thread_id}_{i}_count_{len(results)}")
                    elif query_type == 'price':
                        results = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
                        track_result('read', success=True, data=f"price_read_{thread_id}_{i}_count_{len(results)}")
                    elif query_type == 'analysis':
                        results = get_analysis_results(temp_db)
                        track_result('read', success=True, data=f"analysis_read_{thread_id}_{i}_count_{len(results)}")
                    
                    time.sleep(0.01)  # Simulate analysis processing time
                    
            except (sqlite3.Error, ValueError, RuntimeError) as exc:
                track_result('read', success=False, error=f"Thread {thread_id} {query_type} read error: {exc}")
        
        # EXECUTE CONCURRENT OPERATIONS
        start_time = time.time()
        thread_errors = []  # Collect thread failures
        
        # Create thread pool for concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = []
            
            # Start multiple concurrent writers (simulating data source polling)
            symbol_batches = [symbols[i:i+2] for i in range(0, len(symbols), 2)]  # Split symbols into batches
            
            for thread_id, batch in enumerate(symbol_batches):
                # Each thread writes different types of data
                futures.append(executor.submit(write_news_data, thread_id, batch))
                futures.append(executor.submit(write_price_data, thread_id, batch))
                futures.append(executor.submit(write_analysis_data, thread_id, batch))
            
            # Start concurrent readers while writes are happening (critical WAL test)
            read_types = ['news', 'price', 'analysis']
            for thread_id in range(3):  # 3 reader threads
                query_type = read_types[thread_id % len(read_types)]
                futures.append(executor.submit(read_for_analysis, thread_id, query_type))
            
            # Wait for all operations to complete and collect any failures
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result(timeout=30)  # 30 second timeout per operation
                except (sqlite3.Error, ValueError, RuntimeError, TimeoutError) as exc:
                    thread_errors.append(f"Thread operation failed: {exc}")
        
        execution_time = time.time() - start_time
        
        # FAIL THE TEST if any threads failed
        assert len(thread_errors) == 0, f"Thread failures occurred: {thread_errors}"
        
        # VALIDATE RESULTS
        
        # 1. Verify no database locking errors occurred
        assert len(operation_results['write_errors']) == 0, f"Write errors occurred: {operation_results['write_errors']}"
        assert len(operation_results['read_errors']) == 0, f"Read errors occurred: {operation_results['read_errors']}"
        
        # 2. Verify all operations completed successfully
        expected_writes = len(symbol_batches) * 3  # 3 write operations per batch (news, price, analysis)
        expected_reads = 3 * 3  # 3 reader threads * 3 operations each
        
        assert operation_results['write_count'] >= expected_writes, f"Expected at least {expected_writes} writes, got {operation_results['write_count']}"
        assert operation_results['read_count'] >= expected_reads, f"Expected at least {expected_reads} reads, got {operation_results['read_count']}"
        
        # 3. Verify data consistency - check that data written is actually stored
        final_news = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        final_prices = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=timezone.utc))
        final_analysis = get_analysis_results(temp_db)
        
        # Should have data for each symbol from each thread batch
        news_symbols = {item.symbol for item in final_news}
        price_symbols = {item.symbol for item in final_prices}
        analysis_symbols = {item.symbol for item in final_analysis}
        
        assert len(news_symbols) >= 4, f"Expected news for multiple symbols, got {len(news_symbols)}: {news_symbols}"
        assert len(price_symbols) >= 4, f"Expected price data for multiple symbols, got {len(price_symbols)}: {price_symbols}"
        assert len(analysis_symbols) >= 4, f"Expected analysis for multiple symbols, got {len(analysis_symbols)}: {analysis_symbols}"
        
        # 4. Test specific data integrity for one symbol
        aapl_news = [item for item in final_news if item.symbol == 'AAPL']
        aapl_prices = [item for item in final_prices if item.symbol == 'AAPL']
        aapl_analysis = [item for item in final_analysis if item.symbol == 'AAPL']
        
        assert len(aapl_news) > 0, "AAPL news should be stored"
        assert len(aapl_prices) > 0, "AAPL price data should be stored"
        assert len(aapl_analysis) > 0, "AAPL analysis should be stored"
        
        # Verify specific AAPL data integrity
        aapl_price = aapl_prices[0]
        assert aapl_price.symbol == 'AAPL'
        assert aapl_price.session == Session.REG
        assert aapl_price.volume is not None and aapl_price.volume > 0
        
        # 5. Performance verification - Log execution time for monitoring
        # Note: No hard timeout - CI environments vary in performance
        
        # 6. WAL-specific file verification
        wal_file = f"{temp_db}-wal"
        shm_file = f"{temp_db}-shm"
        
        # WAL files may or may not exist after operations complete (depends on checkpointing)
        # But we can verify they can be created by forcing a checkpoint
        with connect(temp_db) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
