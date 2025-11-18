"""Data model validation tests (pure Python; no database)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data.models import (
    AnalysisResult,
    AnalysisType,
    Holdings,
    NewsEntry,
    NewsItem,
    NewsSymbol,
    NewsType,
    PriceData,
    Session,
    Stance,
)


class TestNewsItem:
    """Test NewsItem model validation."""

    def test_newsitem_valid_creation(self):
        """Valid NewsItem requires url/headline/source/news_type."""
        item = NewsItem(
            url="https://example.com/news/1",
            headline="Apple Stock Rises",
            source="Reuters",
            published=datetime(2024, 1, 15, 10, 30),
            news_type=NewsType.COMPANY_SPECIFIC,
            content="Optional content here",
        )
        assert item.url == "https://example.com/news/1"
        assert item.headline == "Apple Stock Rises"
        assert item.source == "Reuters"
        assert item.published.tzinfo == UTC
        assert item.content == "Optional content here"
        assert item.news_type is NewsType.COMPANY_SPECIFIC

    def test_newsitem_url_validation(self):
        """URL must be http(s)."""
        base_kwargs = {
            "headline": "Test",
            "source": "Test Source",
            "published": datetime.now(),
            "news_type": NewsType.COMPANY_SPECIFIC,
        }

        for url in [
            "http://example.com",
            "https://example.com",
            "https://example.com/path?param=value",
        ]:
            item = NewsItem(url=url, **base_kwargs)
            assert item.url == url

        for url in [
            "ftp://example.com",
            "file:///path/to/file",
            "data:text/plain;base64,SGVsbG8=",
            "javascript:alert(1)",
            "invalid-url",
            "",
        ]:
            with pytest.raises(ValueError, match="url must be http\\(s\\)"):
                NewsItem(url=url, **base_kwargs)

    def test_newsitem_empty_field_validation(self):
        """headline, source, and news_type required after strip()."""
        base_kwargs = {
            "url": "https://example.com",
            "headline": "Test Headline",
            "source": "Test Source",
            "published": datetime.now(),
            "news_type": NewsType.MACRO,
        }

        with pytest.raises(ValueError, match="headline cannot be empty"):
            NewsItem(**{**base_kwargs, "headline": "\t\n"})

        with pytest.raises(ValueError, match="source cannot be empty"):
            NewsItem(**{**base_kwargs, "source": ""})

        item = NewsItem(**{**base_kwargs, "content": "  \n  "})
        assert item.content == "  \n  "

    def test_newsitem_news_type_variants(self):
        """news_type accepts enum instances or exact strings."""
        item_enum = NewsItem(
            url="https://example.com/enum",
            headline="Enum",
            source="Source",
            published=datetime.now(),
            news_type=NewsType.MACRO,
        )
        assert item_enum.news_type is NewsType.MACRO

        item_str = NewsItem(
            url="https://example.com/string",
            headline="String",
            source="Source",
            published=datetime.now(),
            news_type="company_specific",
        )
        assert item_str.news_type is NewsType.COMPANY_SPECIFIC

        with pytest.raises(ValueError, match="valid NewsType"):
            NewsItem(
                url="https://example.com/invalid",
                headline="Invalid",
                source="Source",
                published=datetime.now(),
                news_type="invalid",
            )

    def test_newsitem_timezone_normalization(self):
        """Naive datetimes converted to UTC."""
        naive_dt = datetime(2024, 1, 15, 10, 30)
        item = NewsItem(
            url="https://example.com",
            headline="Test",
            source="Source",
            published=naive_dt,
            news_type=NewsType.COMPANY_SPECIFIC,
        )

        assert item.published.tzinfo == UTC
        assert item.published.year == 2024
        assert item.published.month == 1
        assert item.published.day == 15


class TestNewsEntry:
    """Tests for NewsEntry wrapper semantics."""

    @staticmethod
    def _article() -> NewsItem:
        return NewsItem(
            url="https://example.com/news",
            headline="Headline",
            source="Source",
            published=datetime(2024, 1, 15, 9, 0),
            news_type=NewsType.COMPANY_SPECIFIC,
        )

    def test_newsentry_symbol_uppercasing_and_passthrough(self):
        article = self._article()
        entry = NewsEntry(article=article, symbol="aapl", is_important=None)

        assert entry.symbol == "AAPL"
        assert entry.url == article.url
        assert entry.headline == article.headline
        assert entry.source == article.source
        assert entry.published == article.published
        assert entry.news_type is NewsType.COMPANY_SPECIFIC

    def test_newsentry_is_important_accepts_bool_or_none(self):
        article = self._article()
        assert NewsEntry(article=article, symbol="MSFT", is_important=True).is_important is True
        assert NewsEntry(article=article, symbol="TSLA", is_important=False).is_important is False
        assert NewsEntry(article=article, symbol="GOOG", is_important=None).is_important is None

    def test_newsentry_requires_non_empty_symbol(self):
        article = self._article()
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            NewsEntry(article=article, symbol="  ", is_important=None)

    def test_newsentry_invalid_is_important_value(self):
        article = self._article()
        with pytest.raises(ValueError, match="is_important must be True, False, or None"):
            NewsEntry(article=article, symbol="AAPL", is_important="yes")  # type: ignore[arg-type]


class TestNewsSymbol:
    """Tests for NewsSymbol link validation."""

    def test_newssymbol_valid_creation(self):
        link = NewsSymbol(url="https://example.com/news", symbol="aapl", is_important=None)
        assert link.url == "https://example.com/news"
        assert link.symbol == "AAPL"
        assert link.is_important is None

    def test_newssymbol_importance_bool_conversion(self):
        assert (
            NewsSymbol(
                url="https://example.com/news", symbol="msft", is_important=True
            ).is_important
            is True
        )
        assert (
            NewsSymbol(
                url="https://example.com/news", symbol="msft", is_important=False
            ).is_important
            is False
        )

    def test_newssymbol_invalid_inputs_raise(self):
        with pytest.raises(ValueError, match="url must be http\\(s\\)"):
            NewsSymbol(url="ftp://example.com", symbol="AAPL")

        with pytest.raises(ValueError, match="symbol cannot be empty"):
            NewsSymbol(url="https://example.com", symbol="  ")

        with pytest.raises(ValueError, match="is_important must be True, False, or None"):
            NewsSymbol(url="https://example.com", symbol="AAPL", is_important=2)  # type: ignore[arg-type]


class TestPriceData:
    """Test PriceData model validation"""

    def test_pricedata_symbol_uppercasing(self):
        """Test symbol is automatically uppercased"""
        price = PriceData(symbol="aapl", timestamp=datetime.now(), price=Decimal("150.50"))
        assert price.symbol == "AAPL"

        # Test mixed case
        price2 = PriceData(
            symbol="mSfT", timestamp=datetime.now(), price=Decimal("400.00"), volume=1000
        )
        assert price2.symbol == "MSFT"

    def test_pricedata_price_must_be_positive(self):
        """Test price > 0 validation (not >= 0)"""
        base_data = {"symbol": "AAPL", "timestamp": datetime.now(), "price": Decimal("150.00")}

        # Valid positive price
        item = PriceData(**base_data)
        assert item.price == Decimal("150.00")

        # Zero price should raise ValueError
        with pytest.raises(ValueError, match="price must be > 0"):
            PriceData(**{**base_data, "price": Decimal("0")})

        # Negative price should raise ValueError
        with pytest.raises(ValueError, match="price must be > 0"):
            PriceData(**{**base_data, "price": Decimal("-10.50")})

    def test_pricedata_volume_validation(self):
        """Test volume >= 0 validation (can be None)"""
        base_data = {"symbol": "AAPL", "timestamp": datetime.now(), "price": Decimal("150.00")}

        # Volume can be None
        item = PriceData(**base_data)
        assert item.volume is None

        # Volume can be zero
        item = PriceData(**{**base_data, "volume": 0})
        assert item.volume == 0

        # Volume can be positive
        item = PriceData(**{**base_data, "volume": 1000})
        assert item.volume == 1000

        # Negative volume should raise ValueError
        with pytest.raises(ValueError, match="volume must be >= 0"):
            PriceData(**{**base_data, "volume": -100})

    def test_pricedata_session_enum_validation(self):
        """Test Session enum validation"""
        base_data = {"symbol": "AAPL", "timestamp": datetime.now(), "price": Decimal("150.00")}

        # Valid enum values
        for session in [Session.REG, Session.PRE, Session.POST, Session.CLOSED]:
            item = PriceData(**{**base_data, "session": session})
            assert item.session == session

        # Invalid values (string instead of enum)
        with pytest.raises(ValueError, match="session must be a Session enum value"):
            PriceData(**{**base_data, "session": "REG"})

        # Invalid enum-like object
        with pytest.raises(ValueError, match="session must be a Session enum value"):
            PriceData(**{**base_data, "session": "INVALID"})

    def test_pricedata_decimal_precision(self):
        """Test Decimal type preservation"""
        item = PriceData(symbol="AAPL", timestamp=datetime.now(), price=Decimal("123.456789"))

        # Verify Decimal type preserved
        assert isinstance(item.price, Decimal)
        assert item.price == Decimal("123.456789")

    def test_pricedata_timezone_normalization(self):
        """Test timestamp timezone normalization"""
        naive_dt = datetime(2024, 1, 15, 10, 30)
        item = PriceData(symbol="AAPL", timestamp=naive_dt, price=Decimal("150.00"))

        # Should be converted to UTC
        assert item.timestamp.tzinfo == UTC
        assert item.timestamp.year == 2024
        assert item.timestamp.month == 1
        assert item.timestamp.day == 15

    def test_pricedata_symbol_validation(self):
        """Test symbol stripping and empty validation"""
        base_data = {"timestamp": datetime.now(), "price": Decimal("150.00")}

        # Symbol with whitespace should be trimmed
        item = PriceData(symbol="  AAPL  ", **base_data)
        assert item.symbol == "AAPL"

        # Empty symbol after strip should raise ValueError
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            PriceData(symbol="   ", **base_data)


class TestAnalysisResult:
    """Test AnalysisResult model validation"""

    def test_analysisresult_symbol_uppercasing(self):
        """Test symbol is automatically uppercased"""
        result = AnalysisResult(
            symbol="aapl",
            analysis_type=AnalysisType.NEWS_ANALYSIS,
            model_name="gpt-4",
            stance=Stance.BULL,
            confidence_score=0.85,
            last_updated=datetime.now(),
            result_json='{"test": "data"}',
        )
        assert result.symbol == "AAPL"

        # Test mixed case
        result2 = AnalysisResult(
            symbol="gOoGl",
            analysis_type=AnalysisType.SENTIMENT_ANALYSIS,
            model_name="gemini",
            stance=Stance.NEUTRAL,
            confidence_score=0.5,
            last_updated=datetime.now(),
            result_json='{"analysis": "neutral"}',
        )
        assert result2.symbol == "GOOGL"

    def test_analysisresult_json_validation(self):
        """Test result_json must be valid JSON object"""
        base_data = {
            "symbol": "AAPL",
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.85,
            "last_updated": datetime.now(),
            "result_json": '{"key": "value"}',
        }

        # Valid JSON object
        item = AnalysisResult(**base_data)
        assert item.result_json == '{"key": "value"}'

        # Malformed JSON should raise ValueError
        with pytest.raises(ValueError, match="result_json must be valid JSON"):
            AnalysisResult(**{**base_data, "result_json": '{"invalid": json}'})

        # Non-object JSON (array) should raise ValueError
        with pytest.raises(ValueError, match="result_json must be a JSON object"):
            AnalysisResult(**{**base_data, "result_json": '["not", "an", "object"]'})

        # Non-object JSON (primitive) should raise ValueError
        with pytest.raises(ValueError, match="result_json must be a JSON object"):
            AnalysisResult(**{**base_data, "result_json": '"just a string"'})

        with pytest.raises(ValueError, match="result_json must be a JSON object"):
            AnalysisResult(**{**base_data, "result_json": "42"})

    def test_analysisresult_confidence_range(self):
        """Test confidence_score must be 0.0 <= score <= 1.0"""
        base_data = {
            "symbol": "AAPL",
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "last_updated": datetime.now(),
            "result_json": '{"key": "value"}',
        }

        # Valid range values
        valid_scores = [0.0, 0.5, 1.0, 0.001, 0.999]
        for score in valid_scores:
            item = AnalysisResult(**{**base_data, "confidence_score": score})
            assert item.confidence_score == score

        # Invalid values outside range
        invalid_scores = [-0.1, -1.0, 1.1, 2.0]
        for score in invalid_scores:
            with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
                AnalysisResult(**{**base_data, "confidence_score": score})

    def test_analysisresult_enum_validation(self):
        """Test AnalysisType and Stance enum validation"""
        base_data = {
            "symbol": "AAPL",
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "last_updated": datetime.now(),
            "result_json": '{"key": "value"}',
        }

        # Valid AnalysisType values
        for analysis_type in [
            AnalysisType.NEWS_ANALYSIS,
            AnalysisType.SENTIMENT_ANALYSIS,
            AnalysisType.SEC_FILINGS,
            AnalysisType.HEAD_TRADER,
        ]:
            item = AnalysisResult(**{**base_data, "analysis_type": analysis_type})
            assert item.analysis_type == analysis_type

        # Valid Stance values
        for stance in [Stance.BULL, Stance.BEAR, Stance.NEUTRAL]:
            item = AnalysisResult(**{**base_data, "stance": stance})
            assert item.stance == stance

        # Invalid AnalysisType
        with pytest.raises(ValueError, match="analysis_type must be an AnalysisType enum value"):
            AnalysisResult(**{**base_data, "analysis_type": "news_analysis"})

        # Invalid Stance
        with pytest.raises(ValueError, match="stance must be a Stance enum value"):
            AnalysisResult(**{**base_data, "stance": "BULL"})

    def test_analysisresult_timezone_normalization(self):
        """Test timezone normalization for last_updated and created_at"""
        naive_dt = datetime(2024, 1, 15, 10, 30)
        base_data = {
            "symbol": "AAPL",
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "result_json": '{"key": "value"}',
        }

        # Test last_updated timezone normalization
        item = AnalysisResult(**{**base_data, "last_updated": naive_dt})
        assert item.last_updated is not None
        assert item.last_updated.tzinfo == UTC

        # Test created_at timezone normalization when provided
        item_with_created = AnalysisResult(
            **{**base_data, "last_updated": naive_dt, "created_at": naive_dt}
        )
        assert item_with_created.created_at is not None
        assert item_with_created.created_at.tzinfo == UTC
        assert item_with_created.last_updated is not None
        assert item_with_created.last_updated.tzinfo == UTC

    def test_analysisresult_symbol_validation(self):
        """Test symbol stripping and empty validation"""
        base_data = {
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "last_updated": datetime.now(),
            "result_json": '{"key": "value"}',
        }

        # Symbol with whitespace should be trimmed
        item = AnalysisResult(symbol="  AAPL  ", **base_data)
        assert item.symbol == "AAPL"

        # Empty symbol after strip should raise ValueError
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            AnalysisResult(symbol="   ", **base_data)

    def test_analysisresult_empty_string_validation(self):
        """Test model_name and result_json empty string validation"""
        base_data = {
            "symbol": "AAPL",
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "last_updated": datetime.now(),
        }

        # Empty model_name after strip should raise ValueError
        with pytest.raises(ValueError, match="model_name cannot be empty"):
            AnalysisResult(**{**base_data, "model_name": "   ", "result_json": '{"key": "value"}'})

        # Empty result_json after strip should raise ValueError
        with pytest.raises(ValueError, match="result_json cannot be empty"):
            AnalysisResult(**{**base_data, "model_name": "gpt-4", "result_json": "   "})


class TestHoldings:
    """Test Holdings model validation"""

    def test_holdings_symbol_uppercasing(self):
        """Test symbol is automatically uppercased"""
        holding = Holdings(
            symbol="aapl",
            quantity=Decimal("100"),
            break_even_price=Decimal("150.00"),
            total_cost=Decimal("15000.00"),
        )
        assert holding.symbol == "AAPL"

        # Test mixed case
        holding2 = Holdings(
            symbol="nVdA",
            quantity=Decimal("50"),
            break_even_price=Decimal("500.00"),
            total_cost=Decimal("25000.00"),
            notes="Test holding",
        )
        assert holding2.symbol == "NVDA"

    def test_holdings_financial_values_positive(self):
        """Test quantity > 0, break_even_price > 0, total_cost > 0"""
        base_data = {
            "symbol": "AAPL",
            "quantity": Decimal("100"),
            "break_even_price": Decimal("150.00"),
            "total_cost": Decimal("15000.00"),
        }

        # Valid positive values
        item = Holdings(**base_data)
        assert item.quantity == Decimal("100")
        assert item.break_even_price == Decimal("150.00")
        assert item.total_cost == Decimal("15000.00")

        # Zero quantity should raise ValueError
        with pytest.raises(ValueError, match="quantity must be > 0"):
            Holdings(**{**base_data, "quantity": Decimal("0")})

        # Negative quantity should raise ValueError
        with pytest.raises(ValueError, match="quantity must be > 0"):
            Holdings(**{**base_data, "quantity": Decimal("-10")})

        # Zero break_even_price should raise ValueError
        with pytest.raises(ValueError, match="break_even_price must be > 0"):
            Holdings(**{**base_data, "break_even_price": Decimal("0")})

        # Negative break_even_price should raise ValueError
        with pytest.raises(ValueError, match="break_even_price must be > 0"):
            Holdings(**{**base_data, "break_even_price": Decimal("-50.00")})

        # Zero total_cost should raise ValueError
        with pytest.raises(ValueError, match="total_cost must be > 0"):
            Holdings(**{**base_data, "total_cost": Decimal("0")})

        # Negative total_cost should raise ValueError
        with pytest.raises(ValueError, match="total_cost must be > 0"):
            Holdings(**{**base_data, "total_cost": Decimal("-1000.00")})

    def test_holdings_decimal_precision(self):
        """Test all financial fields maintain Decimal precision"""
        item = Holdings(
            symbol="AAPL",
            quantity=Decimal("123.456789"),
            break_even_price=Decimal("987.654321"),
            total_cost=Decimal("121932.100508"),
        )

        # Verify all are Decimal types with exact precision
        assert isinstance(item.quantity, Decimal)
        assert isinstance(item.break_even_price, Decimal)
        assert isinstance(item.total_cost, Decimal)
        assert item.quantity == Decimal("123.456789")
        assert item.break_even_price == Decimal("987.654321")
        assert item.total_cost == Decimal("121932.100508")

    def test_holdings_timezone_normalization(self):
        """Test timezone normalization for created_at and updated_at"""
        naive_dt = datetime(2024, 1, 15, 10, 30)
        base_data = {
            "symbol": "AAPL",
            "quantity": Decimal("100"),
            "break_even_price": Decimal("150.00"),
            "total_cost": Decimal("15000.00"),
        }

        # Test created_at timezone normalization when provided
        item = Holdings(**{**base_data, "created_at": naive_dt})
        assert item.created_at is not None
        assert item.created_at.tzinfo == UTC

        # Test updated_at timezone normalization when provided
        item = Holdings(**{**base_data, "updated_at": naive_dt})
        assert item.updated_at is not None
        assert item.updated_at.tzinfo == UTC

        # Test both fields together
        item = Holdings(**{**base_data, "created_at": naive_dt, "updated_at": naive_dt})
        assert item.created_at is not None
        assert item.created_at.tzinfo == UTC
        assert item.updated_at is not None
        assert item.updated_at.tzinfo == UTC

    def test_holdings_symbol_validation(self):
        """Test symbol stripping and empty validation"""
        base_data = {
            "quantity": Decimal("100"),
            "break_even_price": Decimal("150.00"),
            "total_cost": Decimal("15000.00"),
        }

        # Symbol with whitespace should be trimmed
        item = Holdings(
            symbol="  AAPL  ",
            quantity=base_data["quantity"],
            break_even_price=base_data["break_even_price"],
            total_cost=base_data["total_cost"],
        )
        assert item.symbol == "AAPL"

        # Empty symbol after strip should raise ValueError
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            Holdings(
                symbol="   ",
                quantity=base_data["quantity"],
                break_even_price=base_data["break_even_price"],
                total_cost=base_data["total_cost"],
            )

    def test_holdings_notes_trimming(self):
        """Test notes field trimming when provided"""
        item = Holdings(
            symbol="AAPL",
            quantity=Decimal("100"),
            break_even_price=Decimal("150.00"),
            total_cost=Decimal("15000.00"),
            notes="  Buy more shares  ",
        )

        # Notes should be trimmed
        assert item.notes == "Buy more shares"
