"""OpenAI LLM provider configuration settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from config.retry import DEFAULT_LLM_RETRY, LLMRetryConfig


@dataclass(frozen=True)
class OpenAISettings:
    """Configuration for OpenAI LLM access."""

    api_key: str
    retry_config: LLMRetryConfig = DEFAULT_LLM_RETRY

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> "OpenAISettings":
        """Load OpenAI settings from environment variables."""
        if env is None:
            env = os.environ
        key = (env.get("OPENAI_API_KEY") or "").strip()
        if not key:
            raise ValueError("OPENAI_API_KEY environment variable not found or empty")
        return OpenAISettings(api_key=key)
