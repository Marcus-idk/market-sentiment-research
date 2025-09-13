"""
Data model validation tests.
Tests all __post_init__ validation logic (pure Python, no database).
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
import json

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings,
    Session, Stance, AnalysisType
)


class TestNewsItem:
    """Test NewsItem model validation"""
    
    def test_newsitem_valid_creation(self):
        """Test valid NewsItem creation with all required fields"""
        item = NewsItem(
            symbol="AAPL",
            url="https://example.com/news/1",
            headline="Apple Stock Rises",
            source="Reuters",
            published=datetime(2024, 1, 15, 10, 30),
            content="Optional content here"
        )
        assert item.symbol == "AAPL"
        assert item.url == "https://example.com/news/1"
        assert item.headline == "Apple Stock Rises"
        assert item.source == "Reuters"
        assert item.published.tzinfo == timezone.utc
        assert item.content == "Optional content here"

    def test_newsitem_url_validation(self):
        """Test URL validation - only HTTP/HTTPS allowed"""
        # Valid URLs
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "https://example.com/path?param=value"
        ]
        
        for url in valid_urls:
            item = NewsItem(
                symbol="AAPL",
                url=url,
                headline="Test",
                source="Test Source",
                published=datetime.now()
            )
            assert item.url == url
            
        # Invalid URLs should raise ValueError
        invalid_urls = [
            "ftp://example.com",
            "file:///path/to/file",
            "data:text/plain;base64,SGVsbG8=",
            "javascript:alert(1)",
            "invalid-url",
            ""
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError, match="url must be http\\(s\\)"):
                NewsItem(
                    symbol="AAPL",
                    url=url,
                    headline="Test",
                    source="Test Source",
                    published=datetime.now()
                )

    def test_newsitem_empty_field_validation(self):
        """Test empty field validation after strip()"""
        base_data = {
            "symbol": "AAPL",
            "url": "https://example.com",
            "headline": "Test Headline",
            "source": "Test Source",
            "published": datetime.now()
        }
        
        # Empty symbol after strip
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            NewsItem(**{**base_data, "symbol": "  "})
            
        # Empty headline after strip
        with pytest.raises(ValueError, match="headline cannot be empty"):
            NewsItem(**{**base_data, "headline": "\t\n"})
            
        # Empty source after strip
        with pytest.raises(ValueError, match="source cannot be empty"):
            NewsItem(**{**base_data, "source": ""})
            
        # NOTE: content is NOT trimmed (per codex correction)
        item = NewsItem(**{**base_data, "content": "  \n  "})
        assert item.content == "  \n  "  # Preserved as-is
    
    def test_newsitem_symbol_uppercasing(self):
        """Test symbol is automatically uppercased"""
        item = NewsItem(
            symbol="aapl",
            url="https://example.com/news",
            headline="Test",
            source="Test",
            published=datetime.now()
        )
        assert item.symbol == "AAPL"
        
        # Test mixed case
        item2 = NewsItem(
            symbol="tSlA",
            url="https://example.com/news2",
            headline="Test",
            source="Test",
            published=datetime.now()
        )
        assert item2.symbol == "TSLA"

    def test_newsitem_timezone_normalization(self):
        """Test naive datetime → UTC conversion"""
        naive_dt = datetime(2024, 1, 15, 10, 30)
        item = NewsItem(
            symbol="AAPL",
            url="https://example.com",
            headline="Test",
            source="Source",
            published=naive_dt
        )
        
        # Should be converted to UTC
        assert item.published.tzinfo == timezone.utc
        assert item.published.year == 2024
        assert item.published.month == 1
        assert item.published.day == 15


class TestPriceData:
    """Test PriceData model validation"""
    
    def test_pricedata_symbol_uppercasing(self):
        """Test symbol is automatically uppercased"""
        price = PriceData(
            symbol="aapl",
            timestamp=datetime.now(),
            price=Decimal("150.50")
        )
        assert price.symbol == "AAPL"
        
        # Test mixed case
        price2 = PriceData(
            symbol="mSfT",
            timestamp=datetime.now(),
            price=Decimal("400.00"),
            volume=1000
        )
        assert price2.symbol == "MSFT"
    
    def test_pricedata_price_must_be_positive(self):
        """Test price > 0 validation (not >= 0)"""
        base_data = {
            "symbol": "AAPL",
            "timestamp": datetime.now(),
            "price": Decimal("150.00")
        }
        
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
        base_data = {
            "symbol": "AAPL",
            "timestamp": datetime.now(),
            "price": Decimal("150.00")
        }
        
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
        base_data = {
            "symbol": "AAPL",
            "timestamp": datetime.now(),
            "price": Decimal("150.00")
        }
        
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
        item = PriceData(
            symbol="AAPL",
            timestamp=datetime.now(),
            price=Decimal("123.456789")
        )
        
        # Verify Decimal type preserved
        assert isinstance(item.price, Decimal)
        assert item.price == Decimal("123.456789")

    def test_pricedata_timezone_normalization(self):
        """Test timestamp timezone normalization"""
        naive_dt = datetime(2024, 1, 15, 10, 30)
        item = PriceData(
            symbol="AAPL",
            timestamp=naive_dt,
            price=Decimal("150.00")
        )
        
        # Should be converted to UTC
        assert item.timestamp.tzinfo == timezone.utc
        assert item.timestamp.year == 2024
        assert item.timestamp.month == 1
        assert item.timestamp.day == 15

    def test_pricedata_symbol_validation(self):
        """Test symbol stripping and empty validation"""
        base_data = {
            "timestamp": datetime.now(),
            "price": Decimal("150.00")
        }
        
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
            result_json='{"test": "data"}'
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
            result_json='{"analysis": "neutral"}'
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
            "result_json": '{"key": "value"}'
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
            AnalysisResult(**{**base_data, "result_json": '42'})

    def test_analysisresult_confidence_range(self):
        """Test confidence_score must be 0.0 <= score <= 1.0"""
        base_data = {
            "symbol": "AAPL",
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "last_updated": datetime.now(),
            "result_json": '{"key": "value"}'
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
            "result_json": '{"key": "value"}'
        }
        
        # Valid AnalysisType values
        for analysis_type in [AnalysisType.NEWS_ANALYSIS, AnalysisType.SENTIMENT_ANALYSIS, 
                            AnalysisType.SEC_FILINGS, AnalysisType.HEAD_TRADER]:
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
            "result_json": '{"key": "value"}'
        }
        
        # Test last_updated timezone normalization
        item = AnalysisResult(**{**base_data, "last_updated": naive_dt})
        assert item.last_updated.tzinfo == timezone.utc
        
        # Test created_at timezone normalization when provided
        item_with_created = AnalysisResult(**{**base_data, "last_updated": naive_dt, "created_at": naive_dt})
        assert item_with_created.created_at.tzinfo == timezone.utc
        assert item_with_created.last_updated.tzinfo == timezone.utc

    def test_analysisresult_symbol_validation(self):
        """Test symbol stripping and empty validation"""
        base_data = {
            "analysis_type": AnalysisType.NEWS_ANALYSIS,
            "model_name": "gpt-4",
            "stance": Stance.BULL,
            "confidence_score": 0.5,
            "last_updated": datetime.now(),
            "result_json": '{"key": "value"}'
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
            "last_updated": datetime.now()
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
            total_cost=Decimal("15000.00")
        )
        assert holding.symbol == "AAPL"
        
        # Test mixed case
        holding2 = Holdings(
            symbol="nVdA",
            quantity=Decimal("50"),
            break_even_price=Decimal("500.00"),
            total_cost=Decimal("25000.00"),
            notes="Test holding"
        )
        assert holding2.symbol == "NVDA"
    
    def test_holdings_financial_values_positive(self):
        """Test quantity > 0, break_even_price > 0, total_cost > 0"""
        base_data = {
            "symbol": "AAPL",
            "quantity": Decimal("100"),
            "break_even_price": Decimal("150.00"),
            "total_cost": Decimal("15000.00")
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
            total_cost=Decimal("121932.100508")
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
            "total_cost": Decimal("15000.00")
        }
        
        # Test created_at timezone normalization when provided
        item = Holdings(**{**base_data, "created_at": naive_dt})
        assert item.created_at.tzinfo == timezone.utc
        
        # Test updated_at timezone normalization when provided
        item = Holdings(**{**base_data, "updated_at": naive_dt})
        assert item.updated_at.tzinfo == timezone.utc
        
        # Test both fields together
        item = Holdings(**{**base_data, "created_at": naive_dt, "updated_at": naive_dt})
        assert item.created_at.tzinfo == timezone.utc
        assert item.updated_at.tzinfo == timezone.utc

    def test_holdings_symbol_validation(self):
        """Test symbol stripping and empty validation"""
        base_data = {
            "quantity": Decimal("100"),
            "break_even_price": Decimal("150.00"),
            "total_cost": Decimal("15000.00")
        }
        
        # Symbol with whitespace should be trimmed
        item = Holdings(symbol="  AAPL  ", **base_data)
        assert item.symbol == "AAPL"
        
        # Empty symbol after strip should raise ValueError
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            Holdings(symbol="   ", **base_data)

    def test_holdings_notes_trimming(self):
        """Test notes field trimming when provided"""
        item = Holdings(
            symbol="AAPL",
            quantity=Decimal("100"),
            break_even_price=Decimal("150.00"),
            total_cost=Decimal("15000.00"),
            notes="  Buy more shares  "
        )
        
        # Notes should be trimmed
        assert item.notes == "Buy more shares"


