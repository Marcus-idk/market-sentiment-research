"""Unit tests for the Gemini LLM provider."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("google.genai")

from config.llm import GeminiSettings
from llm.base import LLMError
from llm.providers import gemini as gemini_module
from llm.providers.gemini import GeminiProvider
from utils.retry import RetryableError

pytestmark = [pytest.mark.asyncio]


def _make_provider(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    thinking_config: dict[str, Any] | None = None,
) -> tuple[GeminiProvider, SimpleNamespace, dict[str, list[dict[str, Any]]]]:
    recorded: dict[str, list[dict[str, Any]]] = {"thinking": [], "config": []}

    class ThinkingConfig:  # pragma: no cover - verified through recorded data
        def __init__(self, **kwargs) -> None:
            recorded["thinking"].append(kwargs)
            self.kwargs = kwargs

    class GenerateContentConfig:  # pragma: no cover - verified through recorded data
        def __init__(self, **kwargs) -> None:
            recorded["config"].append(kwargs)
            self.kwargs = kwargs

    monkeypatch.setattr(gemini_module.types, "ThinkingConfig", ThinkingConfig, raising=False)
    monkeypatch.setattr(
        gemini_module.types,
        "GenerateContentConfig",
        GenerateContentConfig,
        raising=False,
    )

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(
                    return_value=SimpleNamespace(
                        candidates=[
                            SimpleNamespace(
                                content=SimpleNamespace(parts=[SimpleNamespace(text="ok")])
                            )
                        ]
                    )
                ),
                list=AsyncMock(),
            )
        )
    )

    def client_factory(**kwargs):
        return client

    monkeypatch.setattr(gemini_module.genai, "Client", client_factory, raising=False)

    settings = GeminiSettings(api_key="test-key")
    provider = GeminiProvider(
        settings,
        "test-model",
        tools=tools,
        tool_choice=tool_choice,
        thinking_config=thinking_config,
    )
    return provider, client, recorded


class _TestAPIError(gemini_module.APIError):  # type: ignore[misc]
    """Test shim for google-genai APIError preserving isinstance behavior."""

    def __init__(self, msg: str, code: int, headers: dict[str, str] | None = None) -> None:
        Exception.__init__(self, msg)
        self.code = code
        self.headers = headers or {}

    def __str__(self) -> str:  # pragma: no cover - simple passthrough
        return Exception.__str__(self)


class _TestServerError(gemini_module.ServerError):  # type: ignore[misc]
    def __init__(self, msg: str, code: int = 500) -> None:
        Exception.__init__(self, msg)
        self.code = code

    def __str__(self) -> str:  # pragma: no cover
        return Exception.__str__(self)


class _TestClientError(gemini_module.ClientError):  # type: ignore[misc]
    def __init__(self, msg: str, code: int = 400) -> None:
        Exception.__init__(self, msg)
        self.code = code

    def __str__(self) -> str:  # pragma: no cover
        return Exception.__str__(self)


def _api_error(code: int, message: str = "message", headers: dict[str, str] | None = None):
    return _TestAPIError(message, code, headers)


def _server_error(message: str = "server", code: int = 500):
    return _TestServerError(message, code)


def _client_error(message: str = "client", code: int = 400):
    return _TestClientError(message, code)


class TestGeminiProvider:
    @pytest.mark.parametrize(
        "tool_choice, expected_mode",
        [
            ("none", "NONE"),
            ("auto", "AUTO"),
            ("any", "ANY"),
        ],
    )
    async def test_generate_maps_tool_choice(
        self, monkeypatch: pytest.MonkeyPatch, tool_choice: str, expected_mode: str
    ) -> None:
        tools = [{"code_execution": {}}]
        provider, client, recorded = _make_provider(
            monkeypatch,
            tools=tools,
            tool_choice=tool_choice,
        )

        await provider.generate("prompt")

        assert client.aio.models.generate_content.await_count == 1
        config_kwargs = recorded["config"][0]
        tool_config = config_kwargs["tool_config"]
        assert tool_config["function_calling_config"]["mode"] == expected_mode
        if expected_mode == "ANY":
            assert config_kwargs["tools"] == tools

    async def test_generate_requires_tools_for_any(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _ = _make_provider(monkeypatch, tools=None, tool_choice="any")

        with pytest.raises(ValueError, match="tool_choice='any' requires tools"):
            await provider.generate("prompt")

    async def test_generate_uses_default_thinking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, client, recorded = _make_provider(monkeypatch)

        await provider.generate("prompt")

        assert recorded["thinking"][0] == {"thinking_budget": 128}
        assert recorded["config"][0]["candidate_count"] == 1
        assert client.aio.models.generate_content.await_count == 1

    async def test_generate_uses_custom_thinking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = {"thinking_budget": 64, "think_limit": 5}
        provider, _, recorded = _make_provider(
            monkeypatch,
            thinking_config=custom,
        )

        await provider.generate("prompt")

        assert recorded["thinking"][0] == custom

    async def test_generate_raises_when_no_candidates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider, client, _ = _make_provider(monkeypatch)
        client.aio.models.generate_content.return_value = SimpleNamespace(
            candidates=[],
            prompt_feedback="filtered",
        )

        with pytest.raises(LLMError, match="No candidates"):
            await provider.generate("prompt")

    async def test_generate_combines_text_and_code_outputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider, client, _ = _make_provider(monkeypatch)
        client.aio.models.generate_content.return_value = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[
                            SimpleNamespace(text="part 1"),
                            SimpleNamespace(code_execution_result=SimpleNamespace(output="code")),
                        ]
                    )
                )
            ]
        )

        result = await provider.generate("prompt")

        assert result == "part 1\ncode"

    async def test_generate_handles_none_code_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, client, _ = _make_provider(monkeypatch)
        client.aio.models.generate_content.return_value = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[
                            SimpleNamespace(code_execution_result=SimpleNamespace(output=None)),
                        ]
                    )
                )
            ]
        )

        result = await provider.generate("prompt")

        assert result == ""

    async def test_validate_connection_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, client, _ = _make_provider(monkeypatch)
        client.aio.models.list.side_effect = _server_error("offline")

        result = await provider.validate_connection()

        assert result is False

        client.aio.models.list.assert_awaited()

    def test_classify_server_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        exc = _server_error("boom")

        mapped = provider._classify_gemini_exception(exc)

        assert isinstance(mapped, RetryableError)

    @pytest.mark.parametrize(
        "code, expected_retryable",
        [
            (429, True),
            (500, True),
            (502, True),
            (503, True),
            (504, True),
            (408, True),
            (401, False),
            (403, False),
            (400, False),
            (404, False),
            (422, False),
            (418, False),
        ],
    )
    def test_classify_api_error_codes(
        self, monkeypatch: pytest.MonkeyPatch, code: int, expected_retryable: bool
    ) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        exc = _api_error(code)

        mapped = provider._classify_gemini_exception(exc)

        if expected_retryable:
            assert isinstance(mapped, RetryableError)
        else:
            assert isinstance(mapped, LLMError)

    def test_classify_api_error_rate_limit_uses_retry_after(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        headers = {"retry-after": "7"}
        exc = _api_error(429, message="slow down", headers=headers)

        mapped = provider._classify_gemini_exception(exc)

        assert isinstance(mapped, RetryableError)
        assert mapped.retry_after == pytest.approx(7.0)

    def test_classify_client_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        exc = _client_error("bad client")

        mapped = provider._classify_gemini_exception(exc)

        assert isinstance(mapped, LLMError)

    def test_classify_timeout_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        exc = RuntimeError("Request timed out waiting for response")

        mapped = provider._classify_gemini_exception(exc)

        assert isinstance(mapped, RetryableError)

    def test_classify_connection_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        exc = RuntimeError("Connection error occurred")

        mapped = provider._classify_gemini_exception(exc)

        assert isinstance(mapped, RetryableError)

    def test_classify_unexpected_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider, _, _ = _make_provider(monkeypatch)
        exc = ValueError("weird failure")

        mapped = provider._classify_gemini_exception(exc)

        assert isinstance(mapped, LLMError)
