"""Polygon.io API client wrapper."""

import logging
from typing import Any

from config.providers.polygon import PolygonSettings
from utils.http import get_json_with_retry


logger = logging.getLogger(__name__)


class PolygonClient:
    """Minimal async HTTP client wrapper for Polygon.io API calls."""

    def __init__(self, settings: PolygonSettings) -> None:
        self.settings = settings

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
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
        except Exception as exc:
            logger.warning(f"PolygonClient connection validation failed: {exc}")
            return False
