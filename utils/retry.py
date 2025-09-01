import asyncio
import random
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")

class RetryableError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after

async def retry_and_call(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = 4,          # e.g., max_retries + 1
    base: float = 0.25,
    mult: float = 2.0,
    jitter: float = 0.1,
) -> T:
    """Exponential backoff with jitter for retryable operations.

    Retries on RetryableError up to `attempts` times. Sleeps between attempts
    using delay = retry_after (if provided) else base * (mult ** attempt) ± jitter.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return await op()
        except RetryableError as e:
            last_exc = e
            if attempt == attempts - 1:
                raise
            delay = e.retry_after if e.retry_after is not None else max(
                0.1, base * (mult ** attempt) + random.uniform(-jitter, jitter)
            )
            await asyncio.sleep(delay)
    # Should be unreachable; keep mypy happy
    raise last_exc if last_exc else RuntimeError("retry_and_call: no result and no exception")