"""Fixtures and provider specs for LLM integration contract tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from dotenv import load_dotenv

pytest.importorskip("openai")
pytest.importorskip("google.genai")

from config.llm import GeminiSettings, OpenAISettings
from llm import GeminiProvider, OpenAIProvider

load_dotenv(override=True)


@dataclass(slots=True)
class ProviderSpec:
    """Specification describing shared LLM provider behaviors."""

    name: str
    provider_cls: type
    settings_factory: Callable[[], Any]
    model_name: str
    code_tools_factory: Callable[[], list[dict[str, Any]]]
    code_tool_choice_on: str | None
    code_tool_choice_off: str | None
    search_tools_factory: Callable[[], list[dict[str, Any]]]
    search_tool_choice_on: str | None
    search_tool_choice_off: str | None

    def _settings_or_skip(self) -> Any:
        try:
            return self.settings_factory()
        except ValueError as exc:
            pytest.skip(f"{self.name} settings unavailable: {exc}")

    def make_provider(
        self,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ):
        settings = self._settings_or_skip()
        kwargs: dict[str, Any] = {
            "settings": settings,
            "model_name": self.model_name,
        }
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        return self.provider_cls(**kwargs)

    def make_provider_for_code_tools(self, *, enabled: bool):
        tools = self.code_tools_factory() if enabled else None
        tool_choice = self.code_tool_choice_on if enabled else self.code_tool_choice_off
        return self.make_provider(tools=tools, tool_choice=tool_choice)

    def make_provider_for_search(self, *, enabled: bool):
        tools = self.search_tools_factory() if enabled else None
        tool_choice = self.search_tool_choice_on if enabled else self.search_tool_choice_off
        return self.make_provider(tools=tools, tool_choice=tool_choice)


_PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="openai",
        provider_cls=OpenAIProvider,
        settings_factory=OpenAISettings.from_env,
        model_name="gpt-5",
        code_tools_factory=lambda: [{"type": "code_interpreter", "container": {"type": "auto"}}],
        code_tool_choice_on="auto",
        code_tool_choice_off="none",
        search_tools_factory=lambda: [{"type": "web_search_preview"}],
        search_tool_choice_on="auto",
        search_tool_choice_off="none",
    ),
    ProviderSpec(
        name="gemini",
        provider_cls=GeminiProvider,
        settings_factory=GeminiSettings.from_env,
        model_name="gemini-2.5-flash",
        code_tools_factory=lambda: [{"code_execution": {}}],
        code_tool_choice_on=None,
        code_tool_choice_off=None,
        search_tools_factory=lambda: [{"google_search": {}}],
        search_tool_choice_on=None,
        search_tool_choice_off=None,
    ),
)


@pytest.fixture(params=_PROVIDER_SPECS, ids=lambda spec: spec.name)
def provider_spec(request: pytest.FixtureRequest) -> ProviderSpec:
    """Expose provider specs for contract tests."""
    return request.param
