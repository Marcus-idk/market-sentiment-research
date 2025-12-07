import logging
from collections.abc import Mapping
from typing import Any, cast

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from config.llm import GeminiSettings
from llm.base import LLMError, LLMProvider
from utils.retry import RetryableError, parse_retry_after, retry_and_call

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        settings: GeminiSettings,
        model_name: str,
        *,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        thinking_config: Mapping[str, Any] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.settings = settings
        self.model_name = model_name
        self.temperature = temperature
        self.tools = tools
        self.tool_choice = tool_choice
        budget_key = "thinking_budget_token_limit"
        if thinking_config is None:
            self.thinking_config = {budget_key: 128}
        else:
            budget = thinking_config.get(budget_key)
            if isinstance(budget, int):
                clamped = max(128, budget)
                cfg = dict(thinking_config)
                cfg[budget_key] = clamped
                self.thinking_config = cfg
            else:
                self.thinking_config = thinking_config
        self.client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(timeout=settings.retry_config.timeout_seconds * 1000),
        )

    async def generate(self, prompt: str) -> str:
        """Generate a text response from Gemini for the given prompt."""
        args = {"candidate_count": 1, **self.config}

        if self.temperature is not None:
            args["temperature"] = self.temperature

        if self.tools:
            args["tools"] = self.tools

        if self.tool_choice:
            mode = {
                "none": "NONE",
                "auto": "AUTO",
                "any": "ANY",
            }.get(str(self.tool_choice).lower())
            if mode:
                # Check if tools contain function_declarations
                has_function_declarations = any(
                    "function_declarations" in tool for tool in (self.tools or [])
                )

                # Guard: "any" mode requires tools to be provided
                if mode == "ANY" and not self.tools:
                    raise ValueError("tool_choice='any' requires tools to be provided")

                # Guard: tool_choice requires function_declarations
                if not has_function_declarations:
                    raise ValueError(
                        "tool_choice requires function_declarations in tools. "
                        "Built-in tools like code_execution, google_search, and url_context "
                        "do not support tool_choice."
                    )

                args["tool_config"] = {"function_calling_config": {"mode": mode}}

        if self.thinking_config:
            thinking_ctor = cast(Any, types.ThinkingConfig)
            args["thinking_config"] = thinking_ctor(**self.thinking_config)

        config = types.GenerateContentConfig(**args)

        async def _attempt() -> str:
            """Single API call attempt with error mapping to RetryableError."""
            try:
                resp = await self.client.aio.models.generate_content(
                    model=self.model_name, contents=prompt, config=config
                )

                # Check candidates exist before accessing
                if not resp.candidates:
                    # Empty candidates usually means content filtering or API issues
                    safety_msg = ""
                    if hasattr(resp, "prompt_feedback") and resp.prompt_feedback:
                        safety_msg = f" - feedback: {resp.prompt_feedback}"
                    raise LLMError(
                        "No candidates in response - possible content filtering "
                        f"or API issue{safety_msg}"
                    )

                # Extract both text and tool outputs
                candidate = resp.candidates[0]
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None) or []
                out = []
                for p in parts:
                    text = getattr(p, "text", None)
                    if text:
                        out.append(text)
                    code_result = getattr(p, "code_execution_result", None)
                    if code_result:
                        output = getattr(code_result, "output", None) or ""
                        out.append(output)
                return "\n".join(out).strip()

            except (
                APIError,
                ClientError,
                ServerError,
                RetryableError,
                ValueError,
                TypeError,
                RuntimeError,
            ) as exc:
                raise self._classify_gemini_exception(exc) from exc

        # Use retry wrapper with provider's settings
        return await retry_and_call(
            _attempt,
            attempts=self.settings.retry_config.max_retries + 1,
            base=self.settings.retry_config.base,
            mult=self.settings.retry_config.mult,
            jitter=self.settings.retry_config.jitter,
        )

    def _classify_gemini_exception(self, e: Exception) -> Exception:
        """Map Gemini SDK exceptions to RetryableError or LLMError."""
        # ServerError (5xx) is always retryable
        if isinstance(e, ServerError):
            return RetryableError(f"Server error: {str(e)}")

        elif isinstance(e, APIError):
            # Check error code for specific handling
            error_code = getattr(e, "code", None)
            error_msg = str(e)

            # Retryable errors: rate limits, timeouts, server errors
            if error_code == 429:
                # Rate limited - check for retry-after header
                retry_after = None
                headers = getattr(e, "headers", None)
                if headers:
                    retry_after_header = headers.get("retry-after")
                    retry_after = parse_retry_after(retry_after_header)
                return RetryableError(f"Rate limited: {error_msg}", retry_after=retry_after)
            elif error_code in (500, 502, 503, 504):
                # Server errors
                return RetryableError(f"Server error ({error_code}): {error_msg}")
            elif error_code == 408:
                # Request timeout
                return RetryableError(f"Request timeout: {error_msg}")

            # Non-retryable errors: auth failures, bad requests, etc.
            elif error_code == 401:
                return LLMError(f"Authentication failed: {error_msg}")
            elif error_code == 403:
                return LLMError(f"Permission denied: {error_msg}")
            elif error_code == 400:
                return LLMError(f"Invalid request: {error_msg}")
            elif error_code == 404:
                return LLMError(f"Resource not found: {error_msg}")
            elif error_code == 422:
                return LLMError(f"Unprocessable entity: {error_msg}")
            else:
                # Other API errors - don't retry by default
                return LLMError(f"API error ({error_code}): {error_msg}")

        elif isinstance(e, ClientError):
            # Client errors (4xx) are not retryable
            return LLMError(f"Client error: {str(e)}")

        else:
            # Check for common timeout/connection errors by message
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                return RetryableError(f"Request timeout: {error_msg}")
            elif "connection" in error_msg.lower() and "error" in error_msg.lower():
                return RetryableError(f"Connection error: {error_msg}")

            # Unknown error - don't retry
            return LLMError(f"Unexpected error: {error_msg}")

    async def validate_connection(self) -> bool:
        """Return True when Gemini API responds to models.list; False on failure."""
        try:
            await self.client.aio.models.list()
            return True
        except (
            APIError,
            ClientError,
            ServerError,
            RetryableError,
            ValueError,
            TypeError,
            RuntimeError,
        ) as exc:
            logger.warning(f"GeminiProvider connection validation failed: {exc}")
            return False
