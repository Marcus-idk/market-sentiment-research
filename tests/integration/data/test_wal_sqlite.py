"""Validate SQLite WAL mode and concurrent operations under realistic load."""

import concurrent.futures
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal

from data.models import (
    AnalysisResult,
    AnalysisType,
    NewsEntry,
    NewsItem,
    NewsType,
    PriceData,
    Session,
    Stance,
)
from data.storage import (
    connect,
    get_analysis_results,
    get_news_since,
    get_price_data_since,
    store_news_items,
    store_price_data,
    upsert_analysis_result,
)
from data.storage.db_context import _cursor_context


class TestWALSqlite:
    """WAL mode functionality and concurrent operations"""

    @staticmethod
    def _make_news_entry(
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
            content=content,
            published=published,
            source=source,
            news_type=news_type,
        )
        return NewsEntry(article=article, symbol=symbol, is_important=None)

    def test_wal_mode_functionality(self, temp_db):
        """WAL mode is enabled and functional with file-backed DB."""
        # Verify WAL mode is enabled
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

        # Test that WAL files are created during operations
        # Store some data to trigger WAL file creation
        test_news = [
            self._make_news_entry(
                symbol="TEST",
                url="https://example.com/test",
                headline="WAL Test",
                source="Test",
                published=datetime.now(UTC),
            )
        ]
        store_news_items(temp_db, test_news)

        # Verify data was stored successfully (WAL mode working)
        results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        assert len(results) == 1
        assert results[0].symbol == "TEST"
        assert results[0].headline == "WAL Test"

    def test_concurrent_operations_with_wal(self, temp_db):
        """WAL allows concurrent read/write without lock errors and maintains consistency."""

        # VERIFY WAL MODE IS ENABLED
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

        # PREPARE TEST DATA
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        symbols = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ", "META"]

        # Shared results tracking
        operation_results = {
            "write_errors": [],
            "read_errors": [],
            "write_count": 0,
            "read_count": 0,
            "data_written": [],
            "data_read": [],
        }
        operation_lock = threading.Lock()

        def track_result(operation_type, *, success=True, error=None, data=None):
            """Thread-safe result tracking"""
            with operation_lock:
                if operation_type == "write":
                    if success:
                        operation_results["write_count"] += 1
                        if data:
                            operation_results["data_written"].append(data)
                    else:
                        operation_results["write_errors"].append(error)
                elif operation_type == "read":
                    if success:
                        operation_results["read_count"] += 1
                        if data:
                            operation_results["data_read"].append(data)
                    else:
                        operation_results["read_errors"].append(error)

        # SCENARIO 1: MULTIPLE CONCURRENT WRITES (Simulating multiple data source polling)
        def write_news_data(thread_id, symbol_batch):
            """Simulate news data polling from different sources"""
            for i, symbol in enumerate(symbol_batch):
                news_items = [
                    self._make_news_entry(
                        symbol=symbol,
                        url=f"https://newsapi.com/{symbol.lower()}-news-{thread_id}-{i}",
                        headline=f"{symbol} Market Update from Source {thread_id}",
                        content=(
                            f"Latest {symbol} financial news from concurrent source {thread_id}"
                        ),
                        source=f"NewsAPI-{thread_id}",
                        published=base_time,
                    )
                ]

                store_news_items(temp_db, news_items)
                track_result("write", success=True, data=f"news_{symbol}_{thread_id}")

                # Small delay to simulate network latency
                time.sleep(0.01)

        def write_price_data(thread_id, symbol_batch):
            """Simulate price data polling from different exchanges"""
            for i, symbol in enumerate(symbol_batch):
                price_data = [
                    PriceData(
                        symbol=symbol,
                        timestamp=base_time,
                        price=Decimal(f"{100 + thread_id + i}.{thread_id:02d}"),
                        volume=10000 * (thread_id + 1) * (i + 1),
                        session=Session.REG,
                    )
                ]

                store_price_data(temp_db, price_data)
                track_result("write", success=True, data=f"price_{symbol}_{thread_id}")

                time.sleep(0.01)

        def write_analysis_data(thread_id, symbol_batch):
            """Simulate analysis results from different models"""
            for i, symbol in enumerate(symbol_batch):
                analysis = AnalysisResult(
                    symbol=symbol,
                    analysis_type=AnalysisType.NEWS_ANALYSIS,
                    model_name=f"model-{thread_id}",
                    stance=Stance.BULL if (thread_id + i) % 2 == 0 else Stance.BEAR,
                    confidence_score=0.5 + (thread_id * 0.1) + (i * 0.05),
                    last_updated=base_time,
                    result_json=(
                        f'{{"thread": {thread_id}, "symbol": "{symbol}", '
                        f'"analysis": "concurrent_test"}}'
                    ),
                )

                upsert_analysis_result(temp_db, analysis)
                track_result("write", success=True, data=f"analysis_{symbol}_{thread_id}")

                time.sleep(0.01)

        # SCENARIO 2: CONCURRENT READS (Simulating multiple LLM agents analyzing data)
        def read_for_analysis(thread_id, query_type):
            """Simulate LLM agents reading data for analysis"""
            for i in range(3):  # Multiple read operations per thread
                if query_type == "news":
                    results = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
                    track_result(
                        "read",
                        success=True,
                        data=(f"news_read_{thread_id}_{i}_count_{len(results)}"),
                    )
                elif query_type == "price":
                    results = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
                    track_result(
                        "read",
                        success=True,
                        data=f"price_read_{thread_id}_{i}_count_{len(results)}",
                    )
                elif query_type == "analysis":
                    results = get_analysis_results(temp_db)
                    track_result(
                        "read",
                        success=True,
                        data=f"analysis_read_{thread_id}_{i}_count_{len(results)}",
                    )

                time.sleep(0.01)  # Simulate analysis processing time

        # EXECUTE CONCURRENT OPERATIONS
        thread_errors = []  # Collect thread failures

        # Create thread pool for concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = []

            # Start multiple concurrent writers (simulating data source polling)
            symbol_batches = [
                symbols[i : i + 2] for i in range(0, len(symbols), 2)
            ]  # Split symbols into batches

            for thread_id, batch in enumerate(symbol_batches):
                # Each thread writes different types of data
                futures.append(executor.submit(write_news_data, thread_id, batch))
                futures.append(executor.submit(write_price_data, thread_id, batch))
                futures.append(executor.submit(write_analysis_data, thread_id, batch))

            # Start concurrent readers while writes are happening (critical WAL test)
            read_types = ["news", "price", "analysis"]
            for thread_id, query_type in enumerate(read_types):
                futures.append(executor.submit(read_for_analysis, thread_id, query_type))

            # Wait for all operations to complete and collect any failures
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    thread_errors.append(f"Thread operation failed: {exc}")

        # FAIL THE TEST if any threads failed
        assert len(thread_errors) == 0

        # VALIDATE RESULTS

        # 1. Verify no database locking errors occurred
        assert len(operation_results["write_errors"]) == 0
        assert len(operation_results["read_errors"]) == 0

        # 2. Verify all operations completed successfully
        writes_per_batch = sum(len(batch) for batch in symbol_batches)
        expected_writes = writes_per_batch * 3  # One write per symbol for each write helper
        read_iterations = 3  # Each reader performs three queries
        expected_reads = len(read_types) * read_iterations

        assert operation_results["write_count"] == expected_writes
        assert operation_results["read_count"] == expected_reads

        # 3. Verify data consistency - check that data written is actually stored
        final_news = get_news_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        final_prices = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        final_analysis = get_analysis_results(temp_db)

        # Should have data for each symbol from each thread batch
        news_symbols = {item.symbol for item in final_news}
        price_symbols = {item.symbol for item in final_prices}
        analysis_symbols = {item.symbol for item in final_analysis}

        expected_symbol_set = set(symbols)
        assert news_symbols == expected_symbol_set
        assert price_symbols == expected_symbol_set
        assert analysis_symbols == expected_symbol_set

        # 4. Test specific data integrity for one symbol
        aapl_news = [item for item in final_news if item.symbol == "AAPL"]
        aapl_prices = [item for item in final_prices if item.symbol == "AAPL"]
        aapl_analysis = [item for item in final_analysis if item.symbol == "AAPL"]

        assert len(aapl_news) > 0
        assert len(aapl_prices) > 0
        assert len(aapl_analysis) > 0

        # Verify specific AAPL data integrity
        aapl_price = aapl_prices[0]
        assert aapl_price.symbol == "AAPL"
        assert aapl_price.session == Session.REG
        assert aapl_price.volume is not None and aapl_price.volume > 0

        # Force a WAL checkpoint at the end to ensure pending data flushes cleanly
        with connect(temp_db) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
