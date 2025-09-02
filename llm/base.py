from abc import ABC, abstractmethod


class LLMProvider(ABC):

    def __init__(self, **kwargs):
        # Arbitrary provider-specific config passed through to SDK calls
        self.config = kwargs

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        pass

class LLMError(Exception):
    """Non-retryable LLM provider error (auth failures, invalid requests, etc.)"""
    pass
