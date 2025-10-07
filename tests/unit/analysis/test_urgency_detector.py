"""Unit tests for urgency detection module."""

from datetime import datetime, timezone

from data.models import NewsItem
from analysis.urgency_detector import detect_urgency


def test_detect_urgency_returns_empty_list():
    """Test that urgency detector stub returns empty list (no urgent items)."""
    # Create test news items
    news_items = [
        NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="Apple announces bankruptcy",
            published=datetime.now(timezone.utc),
            source="TechNews"
        ),
        NewsItem(
            symbol="MSFT",
            url="https://example.com/news2",
            headline="SEC investigation announced",
            published=datetime.now(timezone.utc),
            source="Finance"
        )
    ]

    # Detect urgency
    urgent_items = detect_urgency(news_items)

    # Verify stub returns empty list (no urgent items)
    assert urgent_items == []


def test_detect_urgency_handles_empty_list():
    """Test urgency detector handles empty input."""
    urgent_items = detect_urgency([])
    assert urgent_items == []


def test_detect_urgency_extracts_text_from_headline_and_content():
    """Test that detector extracts text from both headline and content without crashing."""
    news_items = [
        # Item with headline only (no content)
        NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="Breaking news",
            published=datetime.now(timezone.utc),
            source="TechNews"
        ),
        # Item with headline and content
        NewsItem(
            symbol="MSFT",
            url="https://example.com/news2",
            headline="Microsoft update",
            published=datetime.now(timezone.utc),
            source="Finance",
            content="Detailed content about the update and its implications."
        ),
        # Item with content set to None explicitly
        NewsItem(
            symbol="TSLA",
            url="https://example.com/news3",
            headline="Tesla announcement",
            published=datetime.now(timezone.utc),
            source="AutoNews",
            content=None
        )
    ]

    # Should not crash when extracting text from items with/without content
    urgent_items = detect_urgency(news_items)

    # Verify stub still returns empty (no urgent items)
    assert urgent_items == []
