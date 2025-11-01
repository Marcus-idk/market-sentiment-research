"""
Tests price data storage operations and type handling.
"""

from datetime import UTC, datetime
from decimal import Decimal

from data.models import PriceData, Session
from data.storage import store_price_data
from data.storage.db_context import _cursor_context


class TestPriceDataStorage:
    """Test price data storage operations"""

    def test_store_price_data_type_conversions(self, temp_db):
        """Test price data storage with Decimal and enum conversions"""
        # Create test price data
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
                price=Decimal("150.25"),
                volume=1000000,
                session=Session.REG,
            )
        ]

        # Store price data
        store_price_data(temp_db, items)

        # Verify data stored with proper conversions
        with _cursor_context(temp_db, commit=False) as cursor:
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
        timestamp = datetime(2024, 1, 15, 9, 30, tzinfo=UTC)
        items = [
            PriceData(
                symbol="AAPL",
                timestamp=timestamp,
                price=Decimal("150.00"),
                volume=1000000,
                session=Session.REG,
            ),
            PriceData(
                symbol="AAPL",
                timestamp=timestamp,  # Same timestamp
                price=Decimal("151.00"),  # Different price
                volume=2000000,
                session=Session.PRE,
            ),
        ]

        # Store price data - second item should be ignored (same symbol+timestamp)
        store_price_data(temp_db, items)

        # Verify deduplication worked - first item wins with INSERT OR IGNORE
        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("""
                SELECT COUNT(*), price FROM price_data
                WHERE symbol = 'AAPL' AND timestamp_iso = '2024-01-15T09:30:00Z'
            """)
            count, price = cursor.fetchone()

            assert count == 1, "INSERT OR IGNORE must dedupe duplicate price row"
            assert price == "150.00", "first record should be kept"
