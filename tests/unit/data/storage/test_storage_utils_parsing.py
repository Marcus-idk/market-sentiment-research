"""
Tests for storage_utils parsing and row conversion helpers.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data.models import AnalysisType, NewsEntry, NewsItem, NewsSymbol, NewsType, Session, Stance
from data.storage.storage_utils import (
    _iso_to_datetime,
    _parse_rfc3339,
    _row_to_analysis_result,
    _row_to_holdings,
    _row_to_news_entry,
    _row_to_news_item,
    _row_to_news_symbol,
    _row_to_price_data,
)


class TestIsoParsingHelpers:
    """Tests for ISO/RFC3339 parsing helpers."""

    def test_iso_to_datetime_parses_z_suffix(self):
        dt = _iso_to_datetime("2024-03-10T15:45:00Z")
        assert dt == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)

    def test_iso_to_datetime_preserves_offset(self):
        dt = _iso_to_datetime("2024-03-10T15:45:00+00:00")
        assert dt == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)

    def test_parse_rfc3339_handles_naive_as_utc(self):
        dt = _parse_rfc3339("2024-03-10T15:45:00")
        assert dt == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)

    def test_parse_rfc3339_raises_for_non_string(self):
        with pytest.raises(TypeError):
            _parse_rfc3339(123)  # type: ignore[reportArgumentType] - intentional negative test

    def test_parse_rfc3339_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _parse_rfc3339("not-a-timestamp")


class TestRowMappers:
    """Tests for row-to-model conversion helpers."""

    def test_row_to_news_item_maps_fields_and_type(self):
        row = {
            "url": "https://example.com/news/1",
            "headline": "Headline",
            "published_iso": "2024-03-10T15:45:00Z",
            "source": "Source",
            "content": "Body",
            "news_type": "company_specific",
        }

        result = _row_to_news_item(row)

        assert isinstance(result, NewsItem)
        assert result.url == "https://example.com/news/1"
        assert result.headline == "Headline"
        assert result.published == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)
        assert result.source == "Source"
        assert result.content == "Body"
        assert result.news_type is NewsType.COMPANY_SPECIFIC

    def test_row_to_news_symbol_maps_fields_and_nullable_is_important(self):
        row_true = {
            "url": "https://example.com/news/1",
            "symbol": "aapl",
            "is_important": 1,
        }
        row_null = {
            "url": "https://example.com/news/1",
            "symbol": "msft",
            "is_important": None,
        }

        result_true = _row_to_news_symbol(row_true)
        result_null = _row_to_news_symbol(row_null)

        assert isinstance(result_true, NewsSymbol)
        assert result_true.symbol == "AAPL"
        assert result_true.is_important is True
        assert result_null.symbol == "MSFT"
        assert result_null.is_important is None

    def test_row_to_news_entry_maps_joined_row(self):
        row = {
            "url": "https://example.com/news/1",
            "headline": "Joined Headline",
            "content": "Joined Content",
            "published_iso": "2024-03-10T15:45:00Z",
            "source": "Source",
            "news_type": "macro",
            "symbol": "market",
            "is_important": 0,
        }

        entry = _row_to_news_entry(row)

        assert isinstance(entry, NewsEntry)
        assert entry.symbol == "MARKET"
        assert entry.is_important is False
        assert entry.url == "https://example.com/news/1"
        assert entry.headline == "Joined Headline"
        assert entry.content == "Joined Content"
        assert entry.published == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)
        assert entry.source == "Source"
        assert entry.news_type is NewsType.MACRO

    def test_row_to_price_data_maps_decimal_and_session(self):
        row = {
            "symbol": "msft",
            "timestamp_iso": "2024-03-10T15:45:00Z",
            "price": "310.55",
            "volume": 1500,
            "session": "REG",
        }

        result = _row_to_price_data(row)

        assert result.symbol == "MSFT"
        assert result.price == Decimal("310.55")
        assert result.volume == 1500
        assert result.session == Session.REG

    def test_row_to_analysis_result_builds_model(self):
        row = {
            "symbol": "tsla",
            "analysis_type": "news_analysis",
            "model_name": "gpt",
            "stance": "BULL",
            "confidence_score": 0.85,
            "last_updated_iso": "2024-03-10T15:45:00Z",
            "result_json": '{"text": "ok"}',
            "created_at_iso": "2024-03-10T15:50:00Z",
        }

        result = _row_to_analysis_result(row)

        assert result.symbol == "TSLA"
        assert result.analysis_type == AnalysisType.NEWS_ANALYSIS
        assert result.stance == Stance.BULL
        assert result.confidence_score == pytest.approx(0.85)
        assert result.last_updated == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)
        assert result.created_at == datetime(2024, 3, 10, 15, 50, tzinfo=UTC)

    def test_row_to_holdings_parses_decimals(self):
        row = {
            "symbol": "aapl",
            "quantity": "10.5",
            "break_even_price": "120.00",
            "total_cost": "1260.00",
            "notes": "Long position",
            "created_at_iso": "2024-03-10T15:45:00Z",
            "updated_at_iso": "2024-03-11T09:30:00Z",
        }

        result = _row_to_holdings(row)

        assert result.symbol == "AAPL"
        assert result.quantity == Decimal("10.5")
        assert result.break_even_price == Decimal("120.00")
        assert result.total_cost == Decimal("1260.00")
        assert result.notes == "Long position"
        assert result.created_at == datetime(2024, 3, 10, 15, 45, tzinfo=UTC)
        assert result.updated_at == datetime(2024, 3, 11, 9, 30, tzinfo=UTC)
