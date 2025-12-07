import logging
from collections.abc import Mapping
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from config.llm import OpenAISettings
from llm.base import LLMError, LLMProvider
from utils.retry import RetryableError, parse_retry_after, retry_and_call

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        settings: OpenAISettings,
        model_name: str,
        *,
        temperature: float | None = None,
        reasoning: Mapping[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.settings = settings
        self.model_name = model_name
        self.temperature = temperature
        self.reasoning = reasoning if reasoning is not None else {"effort": "low"}
        self.tools = tools
        self.tool_choice = tool_choice
        self.client = AsyncOpenAI(
            api_key=settings.api_key, max_retries=0, timeout=settings.retry_config.timeout_seconds
        )

    async def generate(self, prompt: str) -> str:
        """Generate a text response from OpenAI for the given prompt."""
        args = {"model": self.model_name, "input": prompt, **self.config}

        if self.temperature is not None:
            args["temperature"] = self.temperature

        if self.reasoning is not None:
            args["reasoning"] = self.reasoning

        if self.tools:
            args["tools"] = self.tools

        if self.tool_choice:
            args["tool_choice"] = self.tool_choice

        # GPT-5 restriction: tool_choice values other than "auto" often reject with 400.
        if isinstance(args.get("tool_choice"), str) and self.model_name.startswith("gpt-5"):
            if args["tool_choice"] != "auto":
                logger.warning(
                    f"tool_choice={args['tool_choice']!r} not supported by {self.model_name}; "
                    "coercing to 'auto'"
                )
                args["tool_choice"] = "auto"

        async def _attempt() -> str:
            """Single API call attempt with error mapping to RetryableError."""
            try:
                resp = await self.client.responses.create(**args)
                return resp.output_text
            except (
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                APIStatusError,
                AuthenticationError,
                PermissionDeniedError,
                BadRequestError,
                NotFoundError,
                UnprocessableEntityError,
                ConflictError,
                RetryableError,
                ValueError,
                TypeError,
                RuntimeError,
            ) as exc:
                raise self._classify_openai_exception(exc) from exc

        # Use retry wrapper with provider's settings
        return await retry_and_call(
            _attempt,
            attempts=self.settings.retry_config.max_retries + 1,
            base=self.settings.retry_config.base,
            mult=self.settings.retry_config.mult,
            jitter=self.settings.retry_config.jitter,
        )

    def _classify_openai_exception(self, e: Exception) -> Exception:
        """Map OpenAI SDK exceptions to RetryableError or LLMError."""
        # Retryable: rate limits with retry-after handling
        if isinstance(e, RateLimitError):
            retry_after = None
            if hasattr(e, "response") and hasattr(e.response, "headers"):
                retry_after_header = e.response.headers.get("retry-after")
                retry_after = parse_retry_after(retry_after_header)
            return RetryableError(f"Rate limited: {str(e)}", retry_after=retry_after)

        # Retryable: transient network issues
        if isinstance(e, APITimeoutError):
            return RetryableError(f"Request timeout: {str(e)}")

        if isinstance(e, APIConnectionError):
            return RetryableError(f"Connection failed: {str(e)}")

        # Retryable: conflicts (409)
        if isinstance(e, ConflictError):
            return RetryableError(f"Conflict error: {str(e)}")

        # HTTP errors: classify by status code
        if isinstance(e, APIStatusError):
            code = getattr(e, "status_code", None)

            # 429 may surface as APIStatusError during streaming/Azure flows.
            if isinstance(code, int) and code == 429:
                retry_after = None
                response = getattr(e, "response", None)
                headers = getattr(response, "headers", None)
                if headers:
                    retry_after_header = headers.get("retry-after")
                    retry_after = parse_retry_after(retry_after_header)
                message = (
                    f"Rate limited ({code}): {str(e)}"
                    if code is not None
                    else f"Rate limited: {str(e)}"
                )
                return RetryableError(message, retry_after=retry_after)

            # 5xx = server errors (retryable)
            if isinstance(code, int) and code >= 500:
                return RetryableError(f"Server error ({code}): {str(e)}")

            # Map status codes to descriptive messages
            error_messages = {
                400: "Invalid request",
                401: "Authentication failed",
                403: "Permission denied",
                404: "Resource not found",
                422: "Unprocessable entity",
                429: "Rate limited",
            }

            # Normalize key to int for lookup to satisfy typing
            label = error_messages.get(code if isinstance(code, int) else -1, "API error")

            # For plain APIStatusError or unknown codes, include the code in the message
            include_code = (type(e) is APIStatusError) or (code not in error_messages)
            code_str = f" ({code})" if include_code and code is not None else ""
            return LLMError(f"{label}{code_str}: {str(e)}")

        # Catch-all for unexpected errors
        return LLMError(f"Unexpected error: {str(e)}")

    async def validate_connection(self) -> bool:
        """Return True when OpenAI models.list succeeds; False when API errors."""
        try:
            await self.client.models.list()
            return True
        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            PermissionDeniedError,
            BadRequestError,
            NotFoundError,
            UnprocessableEntityError,
            ConflictError,
            RetryableError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.warning(f"OpenAIProvider connection validation failed: {exc}")
            return False
