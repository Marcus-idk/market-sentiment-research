import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


def parse_retry_after(value: str | float | int | None) -> float | None:
    """Parse Retry-After header value (numeric seconds or HTTP-date).

    Returns seconds to wait (floored at 0.0), or None if parsing fails.
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    try:
        # Try parsing as numeric seconds (most common: "120")
        return max(0.0, float(value))
    except (TypeError, ValueError):
        # Intentional fallthrough: non-numeric values will try HTTP-date parsing next.
        pass

    try:
        # Try parsing as HTTP-date ("Thu, 01 Dec 2024 15:30:00 GMT")
        if not isinstance(value, str):
            return None
        retry_time = parsedate_to_datetime(value)
        now = datetime.now(UTC)
        seconds = (retry_time - now).total_seconds()
        # Floor at 0.0 to handle past dates (don't wait negative time!)
        return max(0.0, seconds)
    except (ValueError, TypeError, AttributeError) as e:
        # Parsing failed completely, fall back to exponential backoff
        logger.warning(f"Invalid Retry-After header {value!r}: {e}")
        return None


class RetryableError(Exception):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


async def retry_and_call[T](
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = 4,  # e.g., max_retries + 1
    base: float = 0.25,
    mult: float = 2.0,
    jitter: float = 0.1,
) -> T:
    """Exponential backoff with jitter for retryable operations.

    Retries on RetryableError up to `attempts` times. Sleeps between attempts
    using delay = retry_after (if provided) else base * (mult ** attempt) ± jitter.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if base <= 0:
        raise ValueError("base must be > 0")
    if mult < 1.0:
        raise ValueError("mult must be >= 1.0")
    if jitter < 0:
        raise ValueError("jitter must be >= 0")

    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await op()
        except RetryableError as e:
            last_exc = e
            if attempt == attempts - 1:
                raise
            delay = (
                e.retry_after
                if e.retry_after is not None
                else max(0.1, base * (mult**attempt) + random.uniform(-jitter, jitter))
            )
            await asyncio.sleep(delay)
    # Should be unreachable;
    raise last_exc if last_exc else RuntimeError("retry_and_call: no result and no exception")
