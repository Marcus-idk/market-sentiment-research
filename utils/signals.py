"""
Signal handling utilities for graceful shutdown.

Provides cross-platform signal registration for SIGINT (Ctrl+C) and SIGTERM.
"""

import signal
import logging
from typing import Callable

logger = logging.getLogger(__name__)

def register_graceful_shutdown(on_stop: Callable[[], None]) -> Callable[[], None]:
    """
    Register signal handlers for graceful shutdown.
    
    Args:
        on_stop: Callback function to execute when shutdown signal received.
                 Should not take any arguments.
    
    Returns:
        Unregister function that restores default signal handlers.
        Useful for testing and cleanup.
    
    Notes:
        - Registers both SIGINT (Ctrl+C) and SIGTERM handlers
        - SIGINT works on all platforms (Windows, Linux, macOS)
        - SIGTERM mainly used in Linux/containers, limited on Windows
        - The handler logs which signal was received before calling on_stop
    """
    def signal_handler(signum, frame):
        """Handle shutdown signals with logging."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} signal, initiating graceful shutdown...")
        on_stop()
    
    # Store original handlers for restoration
    original_sigint = signal.signal(signal.SIGINT, signal_handler)
    original_sigterm = signal.signal(signal.SIGTERM, signal_handler)
    
    # Return unregister function
    def unregister():
        """Restore original signal handlers."""
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)
    
    return unregister