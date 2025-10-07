"""
Urgency detection module (stub).

For v0.3.3 this is a no-op detector that returns an empty list. It
exists to establish the extension point for future LLM-based analysis.
"""

import logging

from data.models import NewsItem

logger = logging.getLogger(__name__)

def detect_urgency(news_items: list[NewsItem]) -> list[NewsItem]:
    """
    Detect urgent news items that require immediate attention.

    Analyzes headline and content text for urgent keywords.

    Args:
        news_items: List of NewsItem objects to analyze

    Returns:
        List of NewsItem objects flagged as urgent (empty for stub implementation)

    Note:
        Current implementation is a stub that always returns empty list.
        Future versions (v0.5) will use LLM to analyze text for urgent keywords like
        bankruptcy, SEC investigation, etc.
    """
    urgent: list[NewsItem] = []

    if not news_items:
        return urgent

    # Stub loop: exercise basic access; no classification yet
    if logger.isEnabledFor(logging.DEBUG):
        total_chars = 0
        for item in news_items:
            # Access headline/content safely; accumulate length for lightweight debug metric
            total_chars += len(item.headline)
            if item.content:
                total_chars += len(item.content)
        logger.debug(
            f"Analyzed {len(news_items)} news items for urgency (stub) — text_len={total_chars}"
        )

    # Always return empty for v0.3.3
    return urgent
