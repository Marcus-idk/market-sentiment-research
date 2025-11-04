"""Stubs for external LLM SDKs (OpenAI, Google GenAI) used in unit tests."""

import sys
import types


def _ensure_openai_stub() -> None:  # noqa: F811 - exported via __init__.py
    """Install OpenAI SDK stub with simple exception constructors for testing."""
    openai_module = types.ModuleType("openai")

    class AsyncOpenAI:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    class APIError(Exception):
        def __init__(self, message: str = "", *args, **kwargs) -> None:
            super().__init__(message)

    class APIStatusError(APIError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(message)
            self.status_code = status_code
            self.response = response
            self.body = body

    class APIConnectionError(APIError):
        def __init__(self, message: str = "Connection error", *args, **kwargs) -> None:
            super().__init__(message, *args, **kwargs)

    class APITimeoutError(APIError):
        def __init__(self, message: str = "Timeout", *args, **kwargs) -> None:
            super().__init__(message, *args, **kwargs)

    class AuthenticationError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=401 if status_code is None else status_code,
            )

    class PermissionDeniedError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=403 if status_code is None else status_code,
            )

    class BadRequestError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=400 if status_code is None else status_code,
            )

    class NotFoundError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=404 if status_code is None else status_code,
            )

    class UnprocessableEntityError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=422 if status_code is None else status_code,
            )

    class RateLimitError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=429 if status_code is None else status_code,
            )

    class ConflictError(APIStatusError):
        def __init__(
            self,
            message: str,
            *,
            response: object | None = None,
            body: object | None = None,
            status_code: int | None = None,
        ) -> None:
            super().__init__(
                message,
                response=response,
                body=body,
                status_code=409 if status_code is None else status_code,
            )

    # Expose all classes in the stub module
    openai_module.AsyncOpenAI = AsyncOpenAI
    openai_module.APIError = APIError
    openai_module.APIStatusError = APIStatusError
    openai_module.APIConnectionError = APIConnectionError
    openai_module.APITimeoutError = APITimeoutError
    openai_module.AuthenticationError = AuthenticationError
    openai_module.PermissionDeniedError = PermissionDeniedError
    openai_module.BadRequestError = BadRequestError
    openai_module.NotFoundError = NotFoundError
    openai_module.UnprocessableEntityError = UnprocessableEntityError
    openai_module.RateLimitError = RateLimitError
    openai_module.ConflictError = ConflictError
    openai_module.__version__ = "stub"  # Sentinel for safety checks

    # Force override regardless of existing real module
    sys.modules["openai"] = openai_module


def _ensure_google_genai_stub() -> None:  # noqa: F811 - exported via __init__.py
    """Install Google GenAI SDK stub for testing."""
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    types_module = types.ModuleType("google.genai.types")
    errors_module = types.ModuleType("google.genai.errors")

    class Client:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("Client stub must be patched in tests")

    class HttpOptions:  # pragma: no cover
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class ThinkingConfig:  # pragma: no cover
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class GenerateContentConfig:  # pragma: no cover
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class APIError(Exception):
        def __init__(
            self, message: str, *, code: int | None = None, headers: dict | None = None
        ) -> None:
            super().__init__(message)
            self.code = code
            self.headers = headers or {}

    class ClientError(Exception):
        pass

    class ServerError(Exception):
        pass

    google_module.genai = genai_module
    genai_module.Client = Client
    genai_module.types = types_module
    genai_module.errors = errors_module

    types_module.HttpOptions = HttpOptions
    types_module.ThinkingConfig = ThinkingConfig
    types_module.GenerateContentConfig = GenerateContentConfig

    errors_module.APIError = APIError
    errors_module.ClientError = ClientError
    errors_module.ServerError = ServerError

    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = types_module
    sys.modules["google.genai.errors"] = errors_module
