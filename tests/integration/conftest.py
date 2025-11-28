"""Shared pytest configuration for integration tests."""

import pytest

from config.providers.finnhub import FinnhubSettings
from config.providers.polygon import PolygonSettings

pytestmark = pytest.mark.integration


@pytest.fixture
def finnhub_settings() -> FinnhubSettings:
    try:
        return FinnhubSettings.from_env()
    except ValueError as exc:
        pytest.skip(f"FINNHUB settings unavailable: {exc}")


@pytest.fixture
def polygon_settings() -> PolygonSettings:
    try:
        return PolygonSettings.from_env()
    except ValueError as exc:
        pytest.skip(f"POLYGON settings unavailable: {exc}")
