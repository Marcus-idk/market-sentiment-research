"""
Configuration settings for Finnhub API provider
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from config.retry import DEFAULT_DATA_RETRY, DataRetryConfig


@dataclass(frozen=True)
class FinnhubSettings:
    """Configuration settings for Finnhub API integration"""

    api_key: str
    base_url: str = "https://finnhub.io/api/v1"
    retry_config: DataRetryConfig = DEFAULT_DATA_RETRY
    company_news_overlap_minutes: int = 2
    company_news_first_run_days: int = 7
    macro_news_overlap_minutes: int = 2
    macro_news_first_run_days: int = 7

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> "FinnhubSettings":
        """
        Create FinnhubSettings from environment variables

        Args:
            env: Optional environment dict (defaults to os.environ)

        Returns:
            FinnhubSettings instance

        Raises:
            ValueError: If FINNHUB_API_KEY is not found or empty
        """
        if env is None:
            env = os.environ

        api_key = env.get("FINNHUB_API_KEY")
        if not api_key:
            raise ValueError("FINNHUB_API_KEY environment variable not found or empty")

        api_key = api_key.strip()
        if not api_key:
            raise ValueError("FINNHUB_API_KEY environment variable is empty or whitespace")

        return FinnhubSettings(api_key=api_key)
