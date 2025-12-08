"""Unit tests for the news importance stub."""

from analysis.news_importance import label_importance
from tests.factories import make_news_entry


def test_label_importance_marks_all_entries_true():
    """Stub marks every news entry as important."""
    entries = [
        make_news_entry(symbol="AAPL", is_important=None),
        make_news_entry(symbol="MSFT", is_important=False),
    ]

    labeled = label_importance(entries)

    assert len(labeled) == 2
    assert all(entry.is_important is True for entry in labeled)


def test_label_importance_handles_empty_list():
    """Empty input returns empty list."""
    labeled = label_importance([])

    assert labeled == []
