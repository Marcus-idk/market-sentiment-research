"""
Phase 4: Base Class Validation Tests

Tests for abstract base classes and their contracts:
- DataSource abstract base class 
- NewsDataSource and PriceDataSource subclasses
- Exception hierarchy (DataSourceError, RateLimitError)
- Abstract method enforcement
"""

import pytest
from datetime import datetime
from typing import List, Optional

from data.base import (
    DataSource, 
    NewsDataSource, 
    PriceDataSource,
    DataSourceError,
    RateLimitError
)
from data.models import NewsItem, PriceData


class TestDataSourceInitialization:
    """Test DataSource.__init__ validation rules"""
    
    def test_datasource_source_name_none(self):
        with pytest.raises(ValueError, match="source_name cannot be None"):
            class ConcreteSource(DataSource):
                async def validate_connection(self): return True
            ConcreteSource(None)
    
    def test_datasource_source_name_not_string(self):
        with pytest.raises(TypeError, match="source_name must be a string"):
            class ConcreteSource(DataSource):
                async def validate_connection(self): return True
            ConcreteSource(123)
        
        with pytest.raises(TypeError, match="source_name must be a string"):
            class ConcreteSource(DataSource):
                async def validate_connection(self): return True
            ConcreteSource(['list'])
    
    def test_datasource_source_name_empty(self):
        with pytest.raises(ValueError, match="source_name cannot be empty"):
            class ConcreteSource(DataSource):
                async def validate_connection(self): return True
            ConcreteSource("")
        
        with pytest.raises(ValueError, match="source_name cannot be empty"):
            class ConcreteSource(DataSource):
                async def validate_connection(self): return True
            ConcreteSource("   ")
    
    def test_datasource_source_name_too_long(self):
        long_name = "A" * 101
        with pytest.raises(ValueError, match="source_name too long.*101.*max 100"):
            class ConcreteSource(DataSource):
                async def validate_connection(self): return True
            ConcreteSource(long_name)
    
    def test_datasource_source_name_valid(self):
        class ConcreteSource(DataSource):
            async def validate_connection(self): return True
        
        source = ConcreteSource("Finnhub")
        assert source.source_name == "Finnhub"
        
        # Max length exactly 100 chars
        source2 = ConcreteSource("A" * 100)
        assert source2.source_name == "A" * 100
    
    def test_datasource_source_name_trimmed(self):
        class ConcreteSource(DataSource):
            async def validate_connection(self): return True
        
        source = ConcreteSource("  Reuters  ")
        assert source.source_name == "Reuters"


class TestAbstractMethodEnforcement:
    def test_datasource_cannot_instantiate(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class DataSource"):
            DataSource("Test")
    
    def test_newsdata_source_requires_fetch_incremental(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*fetch_incremental"):
            class IncompleteNews(NewsDataSource):
                async def validate_connection(self): return True
            IncompleteNews("Test")
    
    def test_pricedata_source_requires_fetch_incremental(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*fetch_incremental"):
            class IncompletePrice(PriceDataSource):
                async def validate_connection(self): return True
            IncompletePrice("Test")
    
    def test_concrete_implementation_works(self):
        # Complete NewsDataSource implementation
        class ConcreteNews(NewsDataSource):
            async def validate_connection(self) -> bool:
                return True
            
            async def fetch_incremental(self, since: Optional[datetime] = None) -> List[NewsItem]:
                return []
        
        news_source = ConcreteNews("NewsTest")
        assert news_source.source_name == "NewsTest"
        
        # Complete PriceDataSource implementation  
        class ConcretePrice(PriceDataSource):
            async def validate_connection(self) -> bool:
                return True
            
            async def fetch_incremental(self, since: Optional[datetime] = None) -> List[PriceData]:
                return []
        
        price_source = ConcretePrice("PriceTest")
        assert price_source.source_name == "PriceTest"


class TestExceptionHierarchy:
    def test_exception_inheritance(self):
        assert issubclass(DataSourceError, Exception)
        assert issubclass(RateLimitError, DataSourceError)
        assert issubclass(RateLimitError, Exception)
        
        error = DataSourceError("Test error")
        assert isinstance(error, DataSourceError)
        assert isinstance(error, Exception)
        
        rate_error = RateLimitError("Rate limit exceeded")
        assert isinstance(rate_error, RateLimitError)
        assert isinstance(rate_error, DataSourceError)
        assert isinstance(rate_error, Exception)
    
    def test_ratelimit_is_datasource_error(self):
        try:
            raise RateLimitError("API limit reached")
        except DataSourceError as e:
            assert isinstance(e, RateLimitError)
            assert str(e) == "API limit reached"
        except Exception:
            pytest.fail("RateLimitError should be caught as DataSourceError")

