"""
Analysis and classification modules for the trading bot.

This package contains business logic for analyzing and categorizing market data,
including news classification, urgency detection, sentiment analysis, and
trading decisions.
"""

# Public submodules (thin facade; no side effects)
import analysis.news_classifier as news_classifier
import analysis.urgency_detector as urgency_detector

__all__ = [
    "news_classifier",
    "urgency_detector",
]
