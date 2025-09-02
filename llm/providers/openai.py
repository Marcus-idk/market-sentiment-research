from openai import AsyncOpenAI
from openai import (
    RateLimitError,
    APIConnectionError, 
    APITimeoutError,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
    ConflictError
)
from typing import Optional, Union, List, Dict
from ..base import LLMProvider, LLMError
from config.llm import OpenAISettings
from utils.retry import RetryableError, retry_and_call, parse_retry_after


class OpenAIProvider(LLMProvider):
    
    def __init__(
        self,
        settings: OpenAISettings,
        model_name: str,
        temperature: Optional[float] = None,
        reasoning: Optional[Dict] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.settings = settings
        self.model_name = model_name
        self.temperature = temperature
        self.reasoning = reasoning
        self.tools = tools
        self.tool_choice = tool_choice
        # Disable SDK retries - we handle retries ourselves
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            max_retries=0, 
            timeout=settings.retry_config.timeout_seconds
        )

    async def generate(self, prompt: str) -> str:
        args = {"model": self.model_name, "input": prompt, **self.config}

        if self.temperature is not None:
            args["temperature"] = self.temperature

        if self.reasoning is not None:
            args["reasoning"] = self.reasoning

        if self.tools:
            args["tools"] = self.tools

        if self.tool_choice:
            args["tool_choice"] = self.tool_choice

        async def _attempt() -> str:
            """Single API call attempt with error mapping to RetryableError."""
            try:
                resp = await self.client.responses.create(**args)
                return resp.output_text
            except Exception as e:
                raise self._classify_openai_exception(e)
        
        # Use retry wrapper with provider's settings
        return await retry_and_call(
            _attempt,
            attempts=self.settings.retry_config.max_retries + 1,
            base=self.settings.retry_config.base,
            mult=self.settings.retry_config.mult,
            jitter=self.settings.retry_config.jitter
        )

    def _classify_openai_exception(self, e: Exception) -> Exception:
        """Map OpenAI SDK exceptions to RetryableError or LLMError."""
        # Retryable errors: rate limits, timeouts, server errors
        if isinstance(e, RateLimitError):
            # Extract and parse retry-after if available from headers
            retry_after = None
            if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                retry_after_header = e.response.headers.get('retry-after')
                retry_after = parse_retry_after(retry_after_header)
            return RetryableError(f"Rate limited: {str(e)}", retry_after=retry_after)
        
        elif isinstance(e, APITimeoutError):
            return RetryableError(f"Request timeout: {str(e)}")
        
        elif isinstance(e, APIConnectionError):
            return RetryableError(f"Connection failed: {str(e)}")
        
        elif isinstance(e, ConflictError):
            # 409 Conflict - SDK retries this by default, we should too
            return RetryableError(f"Conflict error: {str(e)}")
        
        elif isinstance(e, APIStatusError):
            # Check for 5xx server errors
            if hasattr(e, 'status_code') and e.status_code >= 500:
                return RetryableError(f"Server error ({e.status_code}): {str(e)}")
            # Other status errors are not retryable
            return LLMError(f"API error ({e.status_code}): {str(e)}")
        
        # Non-retryable errors: auth failures, bad requests, etc.
        elif isinstance(e, AuthenticationError):
            return LLMError(f"Authentication failed: {str(e)}")
        
        elif isinstance(e, PermissionDeniedError):
            return LLMError(f"Permission denied: {str(e)}")
        
        elif isinstance(e, BadRequestError):
            return LLMError(f"Invalid request: {str(e)}")
        
        elif isinstance(e, NotFoundError):
            return LLMError(f"Resource not found: {str(e)}")
        
        elif isinstance(e, UnprocessableEntityError):
            return LLMError(f"Unprocessable entity: {str(e)}")
        
        else:
            # Unknown error - don't retry
            return LLMError(f"Unexpected error: {str(e)}")

    async def validate_connection(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
