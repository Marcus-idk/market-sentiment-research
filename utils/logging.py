"""
Centralized logging configuration for the trading bot.

Provides a single setup_logging() function that all entry points can use
to configure logging consistently across the application.
"""

import logging
import os
import sys


def setup_logging() -> None:
    """
    Configure logging for the entire application using environment variables.
    
    Environment variables:
        LOG_LEVEL: Logging level (default: INFO)
                   Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
        LOG_FILE:  Optional file path for logging output
                   If not set, logs only to console
        LOG_FORMAT: Custom format string (default: standard format with timestamp)
    
    Example:
        # In entry script:
        from utils.logging import setup_logging
        setup_logging()
    """
    # Get configuration from environment
    level = os.getenv("LOG_LEVEL", "INFO")
    format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Always include console handler
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Add file handler if LOG_FILE is set
    log_file = os.getenv("LOG_FILE")
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Configure root logger
    logging.basicConfig(
        level=level.upper(),
        format=format,
        handlers=handlers,
        force=True  # Override any existing configuration
    )