"""Finnhub-specific client tests (shared behaviors covered by contracts)."""

from __future__ import annotations

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub.finnhub_client import FinnhubClient

def test_respects_custom_base_url():
    settings = FinnhubSettings(api_key="custom", base_url="https://example.com/base")
    client = FinnhubClient(settings)

    assert client.settings.base_url == "https://example.com/base"
