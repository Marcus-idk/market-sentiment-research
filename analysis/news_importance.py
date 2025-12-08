"""Assign importance flags to news entries (stub implementation)."""

import logging

from data.models import NewsEntry

logger = logging.getLogger(__name__)


def label_importance(news_entries: list[NewsEntry]) -> list[NewsEntry]:
    """Set ``is_important=True`` on every news entry and return the list.

    Notes:
        Stub behavior: marks everything important. This keeps the call site and
        contract in place while a real classifier/LLM is implemented later.
    """

    if not news_entries:
        return news_entries

    for entry in news_entries:
        entry.is_important = True

    logger.debug(f"Marked {len(news_entries)} news entries as important (stub)")
    return news_entries
