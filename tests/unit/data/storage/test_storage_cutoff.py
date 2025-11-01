"""
Tests cutoff/pagination logic for news and price data queries.
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from data.models import NewsEntry, NewsItem, NewsType, PriceData, Session
from data.storage import get_news_before, get_prices_before, store_news_items, store_price_data


def _make_entry(
    *,
    symbol: str,
    url_suffix: str,
    headline: str,
    news_type: NewsType = NewsType.COMPANY_SPECIFIC,
) -> NewsEntry:
    article = NewsItem(
        url=f"https://example.com/{url_suffix}",
        headline=headline,
        source="Source",
        published=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
        news_type=news_type,
        content=None,
    )
    return NewsEntry(article=article, symbol=symbol, is_important=None)


class TestCutoffQueries:
    """Test cutoff-based query operations for batch processing"""

    def test_get_news_before_cutoff_filtering(self, temp_db):
        """Test news retrieval with created_at cutoff filtering for LLM batch processing"""
        # Create news items with different created_at times
        # We need to insert them with delays to ensure different created_at_iso values
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        # First item - oldest
        entry1 = _make_entry(symbol="AAPL", url_suffix="old", headline="Old News")
        store_news_items(temp_db, [entry1])
        time.sleep(1)  # 1 second delay to ensure different created_at

        # Second item - middle
        entry2 = _make_entry(symbol="TSLA", url_suffix="middle", headline="Middle News")
        store_news_items(temp_db, [entry2])

        # Record cutoff time right after second item
        cutoff = datetime.now(UTC)
        time.sleep(1)  # 1 second delay before third item

        # Third item - newest
        entry3 = _make_entry(symbol="AAPL", url_suffix="new", headline="New News")
        store_news_items(temp_db, [entry3])

        # Query news before cutoff (should get first 2 items)
        results = get_news_before(temp_db, cutoff)

        assert len(results) == 2

        # Verify ordering by created_at ASC, then symbol ASC
        assert results[0].headline == "Old News"
        assert results[1].headline == "Middle News"

        # Verify all expected fields are present
        for result in results:
            assert result.symbol in {"AAPL", "TSLA"}
            assert result.url.startswith("https://example.com/")
            assert result.headline
            assert result.published == base_time
            assert result.source == "Source"

    def test_get_news_before_boundary_conditions(self, temp_db):
        """Test get_news_before with boundary conditions using spaced items"""

        # Store first news item
        entry1 = _make_entry(symbol="AAPL", url_suffix="item1", headline="First News")
        store_news_items(temp_db, [entry1])
        time.sleep(1)  # 1 second delay

        # Record time between items
        between_cutoff = datetime.now(UTC)
        time.sleep(1)  # 1 second delay

        # Store second news item
        entry2 = _make_entry(symbol="TSLA", url_suffix="item2", headline="Second News")
        store_news_items(temp_db, [entry2])

        # Test 1: Cutoff before all items (should get nothing)
        past_cutoff = datetime(2020, 1, 1, tzinfo=UTC)
        results = get_news_before(temp_db, past_cutoff)
        assert len(results) == 0

        # Test 2: Cutoff between items (should get first item only)
        results = get_news_before(temp_db, between_cutoff)
        assert len(results) == 1
        assert results[0].headline == "First News"

        # Test 3: Cutoff well after all items (should get both)
        future_cutoff = datetime(2030, 1, 1, tzinfo=UTC)
        results = get_news_before(temp_db, future_cutoff)
        assert len(results) == 2

        # Test 4: Exact timestamp match with current time (should get both items)
        exact_cutoff = datetime.now(UTC)
        results = get_news_before(temp_db, exact_cutoff)
        assert len(results) == 2

    def test_get_prices_before_cutoff_filtering(self, temp_db):
        """Test price data retrieval with created_at cutoff filtering for LLM batch processing"""
        # Create price data with different created_at times
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        # First price - oldest
        price1 = PriceData(
            symbol="AAPL", timestamp=base_time, price=Decimal("150.00"), session=Session.REG
        )
        store_price_data(temp_db, [price1])
        time.sleep(1)  # 1 second delay

        # Second price - middle
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time + timedelta(hours=1),
            price=Decimal("200.00"),
            session=Session.PRE,
        )
        store_price_data(temp_db, [price2])

        # Record cutoff time right after second item
        cutoff = datetime.now(UTC)
        time.sleep(1)  # 1 second delay before third item

        # Third price - newest
        price3 = PriceData(
            symbol="AAPL",
            timestamp=base_time + timedelta(hours=2),
            price=Decimal("151.00"),
            session=Session.POST,
        )
        store_price_data(temp_db, [price3])

        # Query prices before cutoff (should get first 2 items)
        results = get_prices_before(temp_db, cutoff)

        assert len(results) == 2

        # Verify ordering by created_at ASC, then symbol ASC
        assert results[0].price == Decimal("150.00")
        assert results[1].price == Decimal("200.00")

        # Verify all expected fields are present
        for result in results:
            assert hasattr(result, "symbol")
            assert hasattr(result, "timestamp")
            assert hasattr(result, "price")
            assert hasattr(result, "volume")
            assert hasattr(result, "session")

    def test_get_prices_before_boundary_conditions(self, temp_db):
        """Test get_prices_before with boundary conditions using spaced items"""
        base_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        # Store first price data point
        price1 = PriceData(
            symbol="AAPL",
            timestamp=base_time,
            price=Decimal("150.00"),
            volume=1000000,
            session=Session.REG,
        )
        store_price_data(temp_db, [price1])
        time.sleep(1)  # 1 second delay

        # Record time between items
        between_cutoff = datetime.now(UTC)
        time.sleep(1)  # 1 second delay

        # Store second price data point
        price2 = PriceData(
            symbol="TSLA",
            timestamp=base_time + timedelta(hours=1),
            price=Decimal("200.00"),
            volume=2000000,
            session=Session.PRE,
        )
        store_price_data(temp_db, [price2])

        # Test 1: Cutoff before all items (should get nothing)
        past_cutoff = datetime(2020, 1, 1, tzinfo=UTC)
        results = get_prices_before(temp_db, past_cutoff)
        assert len(results) == 0

        # Test 2: Cutoff between items (should get first item only)
        results = get_prices_before(temp_db, between_cutoff)
        assert len(results) == 1
        assert results[0].price == Decimal("150.00")
        assert results[0].symbol == "AAPL"

        # Test 3: Cutoff well after all items (should get both)
        future_cutoff = datetime(2030, 1, 1, tzinfo=UTC)
        results = get_prices_before(temp_db, future_cutoff)
        assert len(results) == 2

        # Test 4: Exact timestamp match with current time (should get both items)
        exact_cutoff = datetime.now(UTC)
        results = get_prices_before(temp_db, exact_cutoff)
        assert len(results) == 2
