"""Polygon.io provider configuration."""

import os
from dataclasses import dataclass
from typing import Mapping

from config.retry import DEFAULT_DATA_RETRY, DataRetryConfig


@dataclass(frozen=True)
class PolygonSettings:
    """Configuration for Polygon.io API access."""

    api_key: str
    base_url: str = "https://api.polygon.io"
    retry_config: DataRetryConfig = DEFAULT_DATA_RETRY

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> "PolygonSettings":
        """
        Create PolygonSettings from environment variables.

        Args:
            env: Optional environment dict (defaults to os.environ)

        Returns:
            PolygonSettings instance

        Raises:
            ValueError: If POLYGON_API_KEY is not found or empty
        """
        if env is None:
            env = os.environ

        api_key = env.get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable not found or empty")

        api_key = api_key.strip()
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable is empty or whitespace")

        return PolygonSettings(api_key=api_key)
