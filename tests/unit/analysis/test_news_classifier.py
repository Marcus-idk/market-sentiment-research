"""Unit tests for the news classifier stub."""

from analysis.news_classifier import classify
from tests.factories import make_news_entry


def test_classify_returns_empty_list_for_any_input():
    """Stub classifier returns empty list regardless of entries provided."""
    entries = [
        make_news_entry(symbol="AAPL", url="https://example.com/news1", headline="Headline 1"),
        make_news_entry(symbol="MSFT", url="https://example.com/news2", headline="Headline 2"),
    ]

    labels = classify(entries)

    assert labels == []


def test_classify_handles_empty_list():
    """Classifier handles empty input without logging debug path."""
    labels = classify([])

    assert labels == []
