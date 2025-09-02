"""
Centralized retry configuration for LLM and data providers
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMRetryConfig:
    """Retry configuration for LLM providers (OpenAI, Gemini, etc.)"""
    timeout_seconds: int = 360  # LLMs need longer timeouts
    max_retries: int = 3
    base: float = 0.25
    mult: float = 2.0
    jitter: float = 0.1


@dataclass(frozen=True)
class DataRetryConfig:
    """Retry configuration for data providers (Finnhub, RSS, etc.)"""
    timeout_seconds: int = 30  # Data APIs are faster
    max_retries: int = 3
    base: float = 0.25
    mult: float = 2.0
    jitter: float = 0.1


# Default instances
DEFAULT_LLM_RETRY = LLMRetryConfig()
DEFAULT_DATA_RETRY = DataRetryConfig()