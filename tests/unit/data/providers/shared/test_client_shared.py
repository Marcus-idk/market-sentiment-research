"""Shared behavior tests for provider API clients."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data import DataSourceError

pytestmark = pytest.mark.asyncio


class TestClientShared:
    """Shared behavior tests for provider clients."""

    async def test_get_builds_url_and_injects_auth(self, client_spec, monkeypatch):
        captured: dict[str, Any] = {}

        async def fake_get_json(url: str, **kwargs: Any) -> dict[str, str]:
            captured.update(
                {
                    "url": url,
                    "params": kwargs.get("params"),
                    "timeout": kwargs.get("timeout"),
                    "max_retries": kwargs.get("max_retries"),
                    "base": kwargs.get("base"),
                    "mult": kwargs.get("mult"),
                    "jitter": kwargs.get("jitter"),
                }
            )
            return {"status": "ok"}

        monkeypatch.setattr(
            f"{client_spec.module_path}.get_json_with_retry",
            fake_get_json,
        )

        client = client_spec.make_client()
        result = await client.get(client_spec.sample_path, dict(client_spec.sample_params))

        expected_params = dict(client_spec.sample_params)
        expected_params[client_spec.auth_param] = client_spec.api_key

        assert result == {"status": "ok"}
        assert captured["url"] == f"{client_spec.base_url}{client_spec.sample_path}"
        assert captured["params"] == expected_params

        retry = client_spec.retry_config
        assert captured["timeout"] == retry.timeout_seconds
        assert captured["max_retries"] == retry.max_retries
        assert captured["base"] == retry.base
        assert captured["mult"] == retry.mult
        assert captured["jitter"] == retry.jitter

    async def test_get_handles_none_params(self, client_spec, monkeypatch):
        captured: dict[str, Any] = {}

        async def fake_get_json(url: str, **kwargs: Any) -> dict[str, str]:
            captured["params"] = kwargs.get("params")
            return {"status": "ok"}

        monkeypatch.setattr(
            f"{client_spec.module_path}.get_json_with_retry",
            fake_get_json,
        )

        client = client_spec.make_client()
        await client.get(client_spec.sample_path, params=None)

        assert captured["params"] == {client_spec.auth_param: client_spec.api_key}

    async def test_validate_connection_success(self, client_spec):
        client = client_spec.make_client()
        client.get = AsyncMock(return_value={"status": "ok"})

        result = await client.validate_connection()

        assert result is True
        if client_spec.validation_params is None:
            client.get.assert_awaited_once_with(client_spec.validation_path)
        else:
            client.get.assert_awaited_once_with(
                client_spec.validation_path,
                client_spec.validation_params,
            )

    async def test_validate_connection_failure_returns_false(self, client_spec):
        client = client_spec.make_client()
        client.get = AsyncMock(side_effect=DataSourceError("boom"))

        result = await client.validate_connection()

        assert result is False

    async def test_get_respects_custom_base_url_override(self, client_spec, monkeypatch):
        """
        Ensure clients honor a non-default base_url from settings
        without provider branching.
        """

        captured_url: dict[str, str] = {}

        async def fake_get_json(url: str, **kwargs: Any) -> dict[str, str]:
            captured_url["url"] = url
            return {"status": "ok"}

        monkeypatch.setattr(
            f"{client_spec.module_path}.get_json_with_retry",
            fake_get_json,
        )

        client = client_spec.make_client()
        custom_base = "https://example.com/custom"

        # Swap in a new settings object with the overridden base_url
        client.settings = replace(client.settings, base_url=custom_base)

        await client.get(client_spec.sample_path, dict(client_spec.sample_params))

        assert captured_url["url"] == f"{custom_base}{client_spec.sample_path}"
