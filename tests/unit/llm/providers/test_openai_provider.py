"""Unit tests for the OpenAI LLM provider."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.llm import OpenAISettings
from llm.base import LLMError
from llm.providers import openai as openai_module
from llm.providers.openai import OpenAIProvider
from utils.retry import RetryableError

pytestmark = [pytest.mark.asyncio]


def _make_provider(
    monkeypatch: pytest.MonkeyPatch, **provider_kwargs
) -> tuple[OpenAIProvider, AsyncMock]:
    client = AsyncMock()
    client.responses = SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(output_text="ok"))
    )
    client.models = SimpleNamespace(list=AsyncMock())
    monkeypatch.setattr(openai_module, "AsyncOpenAI", lambda **_: client)

    settings = OpenAISettings(api_key="test-key")
    provider = OpenAIProvider(settings, "test-model", **provider_kwargs)
    return provider, client


class TestOpenAIProvider:
    async def test_generate_passes_expected_args(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tools = [{"type": "code"}]
        provider, client = _make_provider(
            monkeypatch,
            temperature=0.25,
            tool_choice="auto",
            tools=tools,
            extra_option=True,
        )

        result = await provider.generate("prompt text")

        assert result == "ok"
        assert client.responses.create.await_count == 1
        _, kwargs = client.responses.create.call_args
        assert kwargs["model"] == "test-model"
        assert kwargs["input"] == "prompt text"
        assert kwargs["temperature"] == 0.25
        assert kwargs["reasoning"] == {"effort": "low"}
        assert kwargs["tools"] == tools
        assert kwargs["tool_choice"] == "auto"
        assert kwargs["extra_option"] is True

    async def test_generate_respects_custom_reasoning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider, client = _make_provider(
            monkeypatch,
            temperature=None,
            reasoning={"effort": "medium"},
        )

        await provider.generate("hello")

        _, kwargs = client.responses.create.call_args
        assert "temperature" not in kwargs
        assert kwargs["reasoning"] == {"effort": "medium"}

    def test_classify_rate_limit_with_retry_after(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _ = _make_provider(monkeypatch)
        headers = {"retry-after": "3"}
        exc = openai_module.RateLimitError(
            "Too many requests", response=SimpleNamespace(headers=headers)
        )

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, RetryableError)
        assert mapped.retry_after == pytest.approx(3.0)

    def test_classify_rate_limit_without_retry_after(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _ = _make_provider(monkeypatch)
        exc = openai_module.RateLimitError("Too many requests")

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, RetryableError)
        assert mapped.retry_after is None

    @pytest.mark.parametrize(
        "exception",
        [
            openai_module.APITimeoutError("Timeout"),
            openai_module.APIConnectionError("Connection"),
            openai_module.ConflictError("Conflict"),
        ],
    )
    def test_classify_retryable_errors(
        self, monkeypatch: pytest.MonkeyPatch, exception: Exception
    ) -> None:
        provider, _ = _make_provider(monkeypatch)

        mapped = provider._classify_openai_exception(exception)

        assert isinstance(mapped, RetryableError)

    def test_classify_api_status_retryable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _ = _make_provider(monkeypatch)
        exc = openai_module.APIStatusError("Server", status_code=503)

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, RetryableError)
        assert "503" in str(mapped)

    def test_classify_api_status_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _ = _make_provider(monkeypatch)
        headers = {"retry-after": "2.5"}
        exc = openai_module.APIStatusError(
            "Too many requests",
            status_code=429,
            response=SimpleNamespace(headers=headers),
        )

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, RetryableError)
        assert mapped.retry_after == pytest.approx(2.5)
        assert "429" in str(mapped)

    def test_classify_api_status_non_retryable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _ = _make_provider(monkeypatch)
        exc = openai_module.APIStatusError("Bad request", status_code=400)

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, LLMError)
        assert "400" in str(mapped)

    @pytest.mark.parametrize(
        "exc_cls, expected_message",
        [
            (openai_module.AuthenticationError, "Authentication failed"),
            (openai_module.PermissionDeniedError, "Permission denied"),
            (openai_module.BadRequestError, "Invalid request"),
            (openai_module.NotFoundError, "Resource not found"),
            (openai_module.UnprocessableEntityError, "Unprocessable entity"),
        ],
    )
    def test_classify_non_retryable_openai_errors(
        self, monkeypatch: pytest.MonkeyPatch, exc_cls: type[Exception], expected_message: str
    ) -> None:
        provider, _ = _make_provider(monkeypatch)
        exc = exc_cls("boom")

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, LLMError)
        assert str(mapped).startswith(f"{expected_message}: boom")

    def test_classify_falls_back_to_llm_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _ = _make_provider(monkeypatch)
        exc = ValueError("Unexpected")

        mapped = provider._classify_openai_exception(exc)

        assert isinstance(mapped, LLMError)
        assert "Unexpected error" in str(mapped)

    async def test_validate_connection_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, client = _make_provider(monkeypatch)
        client.models.list.side_effect = openai_module.APIConnectionError("Offline")

        result = await provider.validate_connection()

        assert result is False
        client.models.list.assert_awaited()
