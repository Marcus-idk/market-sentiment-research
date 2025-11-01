"""Shared pytest configuration for integration tests."""

import pytest

from config.providers.finnhub import FinnhubSettings
from config.providers.polygon import PolygonSettings

# Automatically mark every test in this package as integration.
pytestmark = pytest.mark.integration


@pytest.fixture
def finnhub_settings() -> FinnhubSettings:
    """Load Finnhub settings from environment or skip if unavailable."""
    try:
        return FinnhubSettings.from_env()
    except ValueError as exc:
        pytest.skip(f"FINNHUB settings unavailable: {exc}")


@pytest.fixture
def polygon_settings() -> PolygonSettings:
    """Load Polygon settings from environment or skip if unavailable."""
    try:
        return PolygonSettings.from_env()
    except ValueError as exc:
        pytest.skip(f"POLYGON settings unavailable: {exc}")
