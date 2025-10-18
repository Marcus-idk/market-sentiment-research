"""Shared integration tests verifying LLM connection workflows."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.network]


@pytest.mark.asyncio
async def test_provider_validates_connection(provider_spec):
    provider = provider_spec.make_provider()

    assert await provider.validate_connection()


@pytest.mark.asyncio
async def test_provider_generates_basic_response(provider_spec):
    provider = provider_spec.make_provider()
    response = await provider.generate("Say 'test successful'")

    assert isinstance(response, str)
    assert response.strip()
