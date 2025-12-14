"""Base interfaces and errors for LLM providers."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, **kwargs) -> None:
        """Initialize provider with arbitrary config passed to SDK calls."""
        self.config = kwargs

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate text completion from prompt."""
        raise NotImplementedError(
            f"generate() not implemented for prompt={prompt!r}"
        )  # pragma: no cover

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Test if the LLM provider is reachable and credentials work."""
        raise NotImplementedError("validate_connection() must be implemented")  # pragma: no cover


class LLMError(Exception):
    """Non-retryable LLM provider error (auth failures, invalid requests, etc.)"""

    pass
