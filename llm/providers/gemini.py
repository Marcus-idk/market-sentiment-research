import logging
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError
from llm.base import LLMProvider, LLMError
from config.llm import GeminiSettings
from utils.retry import RetryableError, retry_and_call, parse_retry_after


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
        thinking_config: dict[str, Any] | None = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.settings = settings
        self.model_name = model_name
        self.temperature = temperature
        self.tools = tools
        self.tool_choice = tool_choice
        self.thinking_config = thinking_config if thinking_config is not None else {"thinking_budget": 128}
        self.client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(timeout=settings.retry_config.timeout_seconds * 1000)
        )

    async def generate(self, prompt: str) -> str:
        cfg = {
            "candidate_count": 1,
            **self.config
        }
        
        # Only include temperature if not None
        if self.temperature is not None:
            cfg["temperature"] = self.temperature
        
        if self.tools:
            cfg["tools"] = self.tools
            
        if self.tool_choice:
            mode = {"none": "NONE", "auto": "AUTO", "any": "ANY"}.get(str(self.tool_choice).lower())
            if mode:
                # Guard: "any" mode requires tools to be provided
                if mode == "ANY" and not self.tools:
                    raise ValueError("tool_choice='any' requires tools to be provided")
                cfg["tool_config"] = {"function_calling_config": {"mode": mode}}
                    
        if self.thinking_config:
            cfg["thinking_config"] = types.ThinkingConfig(**self.thinking_config)

        config = types.GenerateContentConfig(**cfg)
        
        async def _attempt() -> str:
            """Single API call attempt with error mapping to RetryableError."""
            try:
                resp = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                
                # Check candidates exist before accessing
                if not resp.candidates:
                    # Empty candidates usually means content filtering or API issues
                    safety_msg = ""
                    if hasattr(resp, 'prompt_feedback') and resp.prompt_feedback:
                        safety_msg = f" - feedback: {resp.prompt_feedback}"
                    raise LLMError(f"No candidates in response - possible content filtering or API issue{safety_msg}")
                
                # Extract both text and tool outputs
                parts = resp.candidates[0].content.parts
                out = []
                for p in parts:
                    if getattr(p, "text", None):
                        out.append(p.text)
                    if getattr(p, "code_execution_result", None):
                        out.append(p.code_execution_result.output or "")
                return "\n".join(out).strip()
                
            except Exception as exc:
                raise self._classify_gemini_exception(exc) from exc
        
        # Use retry wrapper with provider's settings
        return await retry_and_call(
            _attempt,
            attempts=self.settings.retry_config.max_retries + 1,
            base=self.settings.retry_config.base,
            mult=self.settings.retry_config.mult,
            jitter=self.settings.retry_config.jitter
        )

    def _classify_gemini_exception(self, e: Exception) -> Exception:
        """Map Gemini SDK exceptions to RetryableError or LLMError."""
        # ServerError (5xx) is always retryable
        if isinstance(e, ServerError):
            return RetryableError(f"Server error: {str(e)}")
        
        elif isinstance(e, APIError):
            # Check error code for specific handling
            error_code = getattr(e, 'code', None)
            error_msg = str(e)
            
            # Retryable errors: rate limits, timeouts, server errors
            if error_code == 429:
                # Rate limited - check for retry-after header
                retry_after = None
                if hasattr(e, 'headers'):
                    retry_after_header = e.headers.get('retry-after')
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
        try:
            await self.client.aio.models.list()
            return True
        except Exception as exc:
            logger.warning(f"GeminiProvider connection validation failed: {exc}")
            return False
