from collections.abc import Mapping
from typing import Any

import httpx

from data import DataSourceError
from utils.retry import RetryableError, parse_retry_after, retry_and_call


async def get_json_with_retry(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float,
    max_retries: int,
    base: float = 0.25,
    mult: float = 2.0,
    jitter: float = 0.1,
) -> Any:
    """Async HTTP GET with retries and JSON parsing.

    Notes:
        Only handles: GET, query params, 200/204, 4xx/5xx, Retry-After, and
        network timeouts. Uses native async HTTP client for non-blocking
        requests.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    if timeout <= 0:
        raise ValueError("timeout must be > 0")
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if base <= 0:
        raise ValueError("base must be > 0")
    if mult < 1.0:
        raise ValueError("mult must be >= 1.0")
    if jitter < 0:
        raise ValueError("jitter must be >= 0")

    async def _op() -> Any:
        """Single HTTP attempt - will be called by retry_and_call up to max_retries+1 times."""
        try:
            # Use native async HTTP client for non-blocking requests
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers, timeout=timeout)

            # SUCCESS CASES
            if response.status_code == 200:
                try:
                    return response.json()  # Parse and return JSON data
                except ValueError as exc:
                    # JSON parsing failed - this is a server/data problem, don't retry
                    raise DataSourceError(f"Invalid JSON response from {url}: {exc}") from exc

            if response.status_code == 204:
                return None  # No Content - valid empty response

            # CLIENT ERRORS (don't retry - our request is bad)
            if response.status_code in (401, 403):
                # Auth failure - retrying won't help, API key is invalid
                raise DataSourceError(f"Authentication failed (status {response.status_code})")

            if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                # Other 4xx errors - bad request, not found, etc. Don't retry.
                raise DataSourceError(f"Client error (status {response.status_code})")

            # RETRYABLE ERRORS (server problems or rate limits)
            if response.status_code in (408, 429) or response.status_code >= 500:
                # Request timeout (408), rate limit (429), or server error (5xx) - retryable
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                raise RetryableError(
                    f"Transient error (status {response.status_code})",
                    retry_after=retry_after,  # Honor server's requested wait time
                )

            # Should never get here, but handle gracefully
            raise DataSourceError(f"Unexpected HTTP status: {response.status_code}")

        # NETWORK PROBLEMS (retryable)
        except httpx.TimeoutException as exc:
            # Request timed out - server might be slow, worth retrying
            raise RetryableError("Network/timeout", retry_after=None) from exc
        except httpx.TransportError as exc:
            # Connection failed - network issue, DNS problem, etc.
            raise RetryableError("Network/timeout", retry_after=None) from exc
        except (RetryableError, DataSourceError):
            # Re-raise our own exceptions unchanged
            raise
        except httpx.HTTPError as exc:
            # Any other HTTP-layer error - treat as non-retryable unless prior branch caught it
            raise DataSourceError(f"Unexpected HTTP error during request: {exc}") from exc

    # Call the retry wrapper - will run _op() up to max_retries+1 times
    # (1 initial attempt + max_retries additional attempts)
    return await retry_and_call(
        _op,
        attempts=max_retries + 1,  # Total attempts (1 + retries)
        base=base,
        mult=mult,
        jitter=jitter,
    )
