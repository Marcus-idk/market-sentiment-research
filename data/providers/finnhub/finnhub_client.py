"""Finnhub API client wrapper."""

from typing import Any

from config.providers.finnhub import FinnhubSettings
from utils.http import get_json_with_retry

class FinnhubClient:
    """Minimal async HTTP client wrapper for Finnhub API calls."""

    def __init__(self, settings: FinnhubSettings) -> None:
        self.settings = settings

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.base_url}{path}"
        params = {**(params or {}), "token": self.settings.api_key}

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
        try:
            await self.get("/quote", {"symbol": "SPY"})
            return True
        except Exception:
            return False

