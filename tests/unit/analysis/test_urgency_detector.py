"""Unit tests for urgency detection module."""

from analysis.urgency_detector import detect_urgency
from tests.factories import make_news_entry


def test_detect_urgency_returns_empty_list():
    """Detector stub returns empty list for populated entries."""
    entries = [
        make_news_entry(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="Headline 1",
            content="Bankruptcy chatter",
        ),
        make_news_entry(
            symbol="MSFT",
            url="https://example.com/news2",
            headline="Headline 2",
        ),
    ]

    urgent_items = detect_urgency(entries)

    assert urgent_items == []


def test_detect_urgency_handles_empty_list():
    """Detector stub handles empty input."""
    urgent_items = detect_urgency([])

    assert urgent_items == []


def test_detect_urgency_extracts_text_from_headline_and_content():
    """Detector accesses headline/content safely even when content is None."""
    entries = [
        make_news_entry(
            symbol="AAPL",
            url="https://example.com/news1",
            headline="Headline 1",
        ),
        make_news_entry(
            symbol="MSFT",
            url="https://example.com/news2",
            headline="Headline 2",
            content="Detailed content about market movement.",
        ),
        make_news_entry(
            symbol="TSLA",
            url="https://example.com/news3",
            headline="Headline 3",
            content=None,
        ),
    ]

    urgent_items = detect_urgency(entries)

    assert urgent_items == []
