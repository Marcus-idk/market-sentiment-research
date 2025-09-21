"""
News classification module.
Currently returns 'Company' for all items - stub for future ML/LLM implementation.
"""

import logging
from typing import List

from data.models import NewsItem, NewsLabel, NewsLabelType

logger = logging.getLogger(__name__)


def classify(news_items: List[NewsItem]) -> List[NewsLabel]:
    """
    Classify news items into categories.

    Args:
        news_items: List of NewsItem objects to classify

    Returns:
        List of NewsLabel objects with classification labels

    Note:
        Current implementation is a stub returning 'Company' for all items.
        Future versions will use heuristics and/or LLM for classification.
    """
    labels = []

    for item in news_items:
        # Stub implementation - always returns Company
        label = NewsLabel(
            symbol=item.symbol,
            url=item.url,
            label=NewsLabelType.COMPANY
        )
        labels.append(label)

    if labels:
        logger.debug(f"Classified {len(labels)} news items (stub mode - all 'Company')")

    return labels
