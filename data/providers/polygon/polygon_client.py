"""Polygon.io API client wrapper."""

import logging
import urllib.parse
from typing import Any

from config.providers.polygon import PolygonSettings
from data import DataSourceError
from utils.http import get_json_with_retry
from utils.retry import RetryableError

logger = logging.getLogger(__name__)

NEWS_LIMIT = 100
NEWS_ORDER = "asc"


def _extract_cursor_from_next_url(next_url: str) -> str | None:
    """Extract cursor parameter value from a Polygon next_url pagination link."""
    try:
        parsed = urllib.parse.urlparse(next_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        return query_params.get("cursor", [None])[0]
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        logger.debug(f"Failed to extract cursor from next_url: {exc}")
        return None


class PolygonClient:
    """Minimal async HTTP client wrapper for Polygon.io API calls."""

    def __init__(self, settings: PolygonSettings) -> None:
        """Store Polygon API settings."""
        self.settings = settings

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform an authenticated GET request to the Polygon API."""
        url = f"{self.settings.base_url}{path}"
        params = {**(params or {}), "apiKey": self.settings.api_key}

        return await get_json_with_retry(
            url,
            params=params,
            timeout=self.settings.retry_config.timeout_seconds,
            max_retries=self.settings.retry_config.max_retries,
            base=self.settings.retry_config.base,
            mult=self.settings.retry_config.mult,
            jitter=self.settings.retry_config.jitter,
        )

    async def validate_connection(self) -> bool:
        """Validate API connection using market status endpoint."""
        try:
            await self.get("/v1/marketstatus/now")
            return True
        except (DataSourceError, RetryableError, ValueError, TypeError) as exc:
            logger.warning(f"PolygonClient connection validation failed: {exc}")
            return False
