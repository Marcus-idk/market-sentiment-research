"""Finnhub-specific price provider tests (shared behaviors covered by contracts)."""

from __future__ import annotations

import pytest

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubPriceProvider


@pytest.mark.asyncio
async def test_fetch_incremental_with_no_symbols_returns_empty_list():
    provider = FinnhubPriceProvider(FinnhubSettings(api_key="test_key"), [])

    result = await provider.fetch_incremental()

    assert result == []

