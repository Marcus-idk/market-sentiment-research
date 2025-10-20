"""Polygon-specific macro news tests (complement contract coverage)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from config.providers.polygon import PolygonSettings
from data.providers.polygon import PolygonMacroNewsProvider
from data.storage.storage_utils import _datetime_to_iso


class TestPolygonMacroNewsProvider:
    """Targeted Polygon-only behaviors not covered by contracts."""

    @pytest.mark.asyncio
    async def test_fetch_incremental_handles_pagination(self, monkeypatch):
        settings = PolygonSettings(api_key="test_key")
        provider = PolygonMacroNewsProvider(settings, ["AAPL"])

        fixed_now = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr(
            "data.providers.polygon.polygon_macro_news.datetime",
            MockDatetime,
        )

        now_iso = _datetime_to_iso(fixed_now)
        page1 = {
            "results": [
                {
                    "title": "A",
                    "article_url": "https://example.com/a",
                    "published_utc": now_iso,
                    "tickers": ["AAPL"],
                    "publisher": {"name": "SourceA"},
                    "description": "Desc A",
                }
            ],
            "next_url": "https://api.polygon.io/v2/reference/news?cursor=abc123",
        }
        page2 = {
            "results": [
                {
                    "title": "B",
                    "article_url": "https://example.com/b",
                    "published_utc": now_iso,
                    "tickers": ["AAPL"],
                    "publisher": {"name": "SourceB"},
                    "description": "Desc B",
                }
            ]
        }

        responses = [page1, page2]
        call_count = {"n": 0}

        async def mock_get(path: str, params: dict | None = None):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        provider.client.get = mock_get  # type: ignore[attr-defined]

        result = await provider.fetch_incremental()

        # Each page yields one NewsItem mapped to 'AAPL'
        assert len(result) == 2
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "next_url,expected",
        [
            ("https://api.polygon.io/v2/reference/news?cursor=abc123", "abc123"),
            (
                "https://api.polygon.io/v2/reference/news?other=val&cursor=xyz",
                "xyz",
            ),
            ("https://api.polygon.io/v2/reference/news?nocursor", None),
            ("not a url", None),
        ],
    )
    async def test_extract_cursor_from_next_url(self, next_url: str, expected: str | None):
        settings = PolygonSettings(api_key="test_key")
        provider = PolygonMacroNewsProvider(settings, ["AAPL"])  # watchlist

        cursor = provider._extract_cursor(next_url)
        assert cursor == expected

