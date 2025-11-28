"""Contract tests for basic LLM connectivity."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_provider_validates_connection(provider_spec):
    """Test provider validates connection."""
    provider = provider_spec.make_provider()

    assert await provider.validate_connection()


async def test_provider_generates_basic_response(provider_spec):
    """Test provider generates basic response."""
    provider = provider_spec.make_provider()
    response = await provider.generate("Say 'test successful'")

    assert isinstance(response, str)
    assert response.strip()
