"""Finnhub-specific price provider tests (shared behaviors covered by shared tests)."""

from __future__ import annotations

import pytest

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubPriceProvider


pytestmark = pytest.mark.asyncio


@pytest.fixture
def price_provider() -> FinnhubPriceProvider:
    """Create a FinnhubPriceProvider with no symbols for focused tests."""

    settings = FinnhubSettings(api_key="test_key")
    return FinnhubPriceProvider(settings, [])


class TestFinnhubPriceProviderSpecific:
    """Finnhub-only behaviors not exercised by the shared price contract tests."""

    async def test_fetch_incremental_with_no_symbols_returns_empty_list(
        self, price_provider: FinnhubPriceProvider
    ) -> None:
        result = await price_provider.fetch_incremental()

        assert result == []

