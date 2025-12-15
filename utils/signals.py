"""Signal handling utilities for graceful shutdown."""

import logging
import signal
from collections.abc import Callable
from types import FrameType

logger = logging.getLogger(__name__)


def register_graceful_shutdown(on_stop: Callable[[], None]) -> Callable[[], None]:
    """Register SIGINT/SIGTERM handlers and return unregister callback."""

    def signal_handler(signum: int, _frame: FrameType | None) -> None:
        """Handle shutdown signals with logging."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s signal, initiating graceful shutdown...", sig_name)
        on_stop()

    # Store original handlers for restoration
    original_sigint = signal.signal(signal.SIGINT, signal_handler)
    original_sigterm = signal.signal(signal.SIGTERM, signal_handler)

    # Return unregister function
    def unregister() -> None:
        """Restore original signal handlers."""
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)

    return unregister
