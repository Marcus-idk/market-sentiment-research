"""Finnhub-specific company news tests (contract coverage handled elsewhere)."""

from __future__ import annotations

import pytest

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubNewsProvider


class TestFinnhubNewsProviderSpecific:
    """Tests for Finnhub-only behaviors not covered by company news contracts."""

    @pytest.mark.asyncio
    async def test_fetch_incremental_with_no_symbols_returns_empty_list(self):
        provider = FinnhubNewsProvider(FinnhubSettings(api_key="test_key"), [])

        result = await provider.fetch_incremental()

        assert result == []
