from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from .models import NewsItem, PriceData


class DataSource(ABC):
    """
    Abstract base class for all data providers (Finnhub, RSS, Reddit, etc.)
    
    Defines the contract that every data source must implement:
    - Incremental fetching (only get new data since last fetch)
    - Connection validation 
    - Consistent error handling
    """
    
    def __init__(self, source_name: str):
        """
        Initialize data source with identifying name
        
        Args:
            source_name: Human-readable identifier (e.g., "Finnhub", "RSS_Reuters")
            
        Raises:
            ValueError: If source_name is invalid (None, empty, too long, or contains invalid characters)
            TypeError: If source_name is not a string
        """
        if source_name is None:
            raise ValueError("source_name cannot be None")
        if not isinstance(source_name, str):
            raise TypeError(f"source_name must be a string, got {type(source_name).__name__}")
        if not source_name.strip():
            raise ValueError("source_name cannot be empty or whitespace only")
        if len(source_name) > 100:
            raise ValueError(f"source_name too long: {len(source_name)} characters (max 100)")
        
        self.source_name = source_name.strip()
    
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Test if the data source is reachable and credentials work
        
        Returns:
            True if connection successful, False otherwise
            
        Note:
            Should not raise exceptions - return False for any connection issues
        """
        pass
    
    pass


class DataSourceError(Exception):
    """Base exception for data source related errors"""
    pass


class NewsDataSource(DataSource):
    """Abstract base class for data sources that provide news content"""
    
    @abstractmethod
    async def fetch_incremental(self, since: Optional[datetime] = None) -> List[NewsItem]:
        """Fetch new news items since the specified timestamp"""
        pass


class PriceDataSource(DataSource):
    """Abstract base class for data sources that provide price/market data"""
    
    @abstractmethod
    async def fetch_incremental(self, since: Optional[datetime] = None) -> List[PriceData]:
        """Fetch new price data since the specified timestamp"""
        pass
