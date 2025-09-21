"""Unit tests for news classification module."""

from datetime import datetime, timezone

from data.models import NewsItem, NewsLabelType
from analysis.news_classifier import classify


def test_classify_returns_company_for_all():
    """Test that classifier stub returns Company label for all news."""
    # Create test news items
    news_items = [
        NewsItem(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="Apple announces new product",
            published=datetime.now(timezone.utc),
            source="TechNews"
        ),
        NewsItem(
            symbol="MSFT",
            url="https://example.com/news2",
            headline="Microsoft earnings report",
            published=datetime.now(timezone.utc),
            source="Finance"
        )
    ]

    # Classify
    labels = classify(news_items)

    # Verify all labeled as Company (stub behavior)
    assert len(labels) == 2
    assert all(label.label == NewsLabelType.COMPANY for label in labels)
    assert labels[0].symbol == "AAPL"
    assert labels[0].url == "https://example.com/news1"
    assert labels[1].symbol == "MSFT"
    assert labels[1].url == "https://example.com/news2"


def test_classify_empty_list():
    """Test classifier handles empty input."""
    labels = classify([])
    assert labels == []
    