"""Gemini LLM provider configuration settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from config.retry import DEFAULT_LLM_RETRY, LLMRetryConfig


@dataclass(frozen=True)
class GeminiSettings:
    """Configuration for Gemini LLM access."""

    api_key: str
    retry_config: LLMRetryConfig = DEFAULT_LLM_RETRY

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> "GeminiSettings":
        """Load Gemini settings from environment variables."""
        if env is None:
            env = os.environ
        key = (env.get("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable not found or empty")
        return GeminiSettings(api_key=key)
