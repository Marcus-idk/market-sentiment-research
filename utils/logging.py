"""Centralized logging configuration for the Market Sentiment Analyzer."""

import logging
import os
import sys


def setup_logging() -> None:
    """Configure root logger from environment variables."""
    # Get configuration from environment
    level = os.getenv("LOG_LEVEL", "INFO")
    fmt = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Always include console handler
    handlers = [logging.StreamHandler(sys.stdout)]

    # Add file handler if LOG_FILE is set
    log_file = os.getenv("LOG_FILE")
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    # Configure root logger
    logging.basicConfig(
        level=level.upper(),
        format=fmt,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )
