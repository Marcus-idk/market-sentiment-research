"""Polygon-specific company news tests (complement contract coverage)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from config.providers.polygon import PolygonSettings
from data.providers.polygon import PolygonNewsProvider
from data.storage.storage_utils import _datetime_to_iso

pytestmark = pytest.mark.asyncio


class TestPolygonNewsProvider:
    """Targeted Polygon-only behaviors not covered by contracts."""

    async def test_fetch_incremental_handles_pagination(self, monkeypatch):
        settings = PolygonSettings(api_key="test_key")
        provider = PolygonNewsProvider(settings, ["AAPL"])

        fixed_now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now

            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)

        monkeypatch.setattr(
            "data.providers.polygon.polygon_news.datetime",
            MockDatetime,
        )

        now_iso = _datetime_to_iso(fixed_now)
        page1 = {
            "results": [
                {
                    "title": "A",
                    "article_url": "https://example.com/a",
                    "published_utc": now_iso,
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

        provider.client.get = mock_get

        result = await provider.fetch_incremental()

        assert len(result) == 2
        assert call_count["n"] == 2
        assert all(item.is_important is True for item in result)

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
        provider = PolygonNewsProvider(settings, ["AAPL"])

        cursor = provider._extract_cursor(next_url)
        assert cursor == expected

    async def test_fetch_symbol_news_applies_buffer_filter(self, monkeypatch, caplog):
        settings = PolygonSettings(api_key="test_key")
        provider = PolygonNewsProvider(settings, ["AAPL"])
        buffer_time = datetime(2024, 1, 20, 12, 0, tzinfo=UTC)
        early = (buffer_time - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        late = (buffer_time + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

        response = {
            "results": [
                {
                    "title": "Too Old",
                    "article_url": "https://example.com/old",
                    "published_utc": early,
                    "publisher": {"name": "Polygon"},
                    "description": "",
                },
                {
                    "title": "Fresh",
                    "article_url": "https://example.com/new",
                    "published_utc": late,
                    "publisher": {"name": "Polygon"},
                    "description": "Desc",
                },
            ]
        }

        async def mock_get(path: str, params: dict | None = None):
            return response

        provider.client.get = mock_get

        caplog.set_level(logging.WARNING)
        result = await provider._fetch_symbol_news(
            "AAPL",
            "2024-01-01T00:00:00Z",
            buffer_time,
        )

        assert len(result) == 1
        assert result[0].article.headline == "Fresh"
        assert "published=" in caplog.text
