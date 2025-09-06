from typing import Any, Dict, Optional

import httpx

from data.base import DataSourceError
from utils.retry import RetryableError, retry_and_call, parse_retry_after


async def get_json_with_retry(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: float,
    max_retries: int,
    base: float = 0.25,
    mult: float = 2.0,
    jitter: float = 0.1,
) -> Any:
    """Async HTTP GET with retries and JSON parsing.

    Only handles: GET, query params, 200/204, 4xx/5xx, Retry-After, and network timeouts.
    Uses native async HTTP client for non-blocking requests.
    """

    async def _op() -> Any:
        """Single HTTP attempt - will be called by retry_and_call up to max_retries+1 times."""
        try:
            # Use native async HTTP client for non-blocking requests
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=timeout)

            # SUCCESS CASES
            if response.status_code == 200:
                try:
                    return response.json()  # Parse and return JSON data
                except Exception as e:
                    # JSON parsing failed - this is a server/data problem, don't retry
                    raise DataSourceError(f"Invalid JSON response from {url}: {e}")

            if response.status_code == 204:
                return None  # No Content - valid empty response

            # CLIENT ERRORS (don't retry - our request is bad)
            if response.status_code in (401, 403):
                # Auth failure - retrying won't help, API key is invalid
                raise DataSourceError(f"Authentication failed (status {response.status_code})")

            if 400 <= response.status_code < 500 and response.status_code != 429:
                # Other 4xx errors - bad request, not found, etc. Don't retry.
                raise DataSourceError(f"Client error (status {response.status_code})")

            # RETRYABLE ERRORS (server problems or rate limits)
            if response.status_code == 429 or response.status_code >= 500:
                # Rate limit (429) or server error (5xx) - these can be temporary
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                raise RetryableError(
                    f"Transient error (status {response.status_code})",
                    retry_after=retry_after,  # Honor server's requested wait time
                )

            # Should never get here, but handle gracefully
            raise DataSourceError(f"Unexpected HTTP status: {response.status_code}")

        # NETWORK PROBLEMS (retryable)
        except httpx.TimeoutException:
            # Request timed out - server might be slow, worth retrying
            raise RetryableError("Network/timeout", retry_after=None)
        except httpx.TransportError:
            # Connection failed - network issue, DNS problem, etc.
            raise RetryableError("Network/timeout", retry_after=None)
        except (RetryableError, DataSourceError):
            # Re-raise our own exceptions unchanged
            raise
        except Exception as e:
            # Any other unexpected error - don't retry unknown problems
            raise DataSourceError(f"Unexpected error during HTTP request: {e}")

    # Call the retry wrapper - will run _op() up to max_retries+1 times
    # (1 initial attempt + max_retries additional attempts)
    return await retry_and_call(
        _op,
        attempts=max_retries + 1,  # Total attempts (1 + retries)
        base=base,
        mult=mult,
        jitter=jitter,
    )
