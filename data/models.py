from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal


@dataclass
class NewsItem:
    """Data model for news articles from various sources."""
    
    title: str
    content: str
    timestamp: datetime
    source: str
    url: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[list[str]] = None
    unique_id: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.title or not self.title.strip():
            raise ValueError("title cannot be empty")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if not self.source or not self.source.strip():
            raise ValueError("source cannot be empty")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be datetime object")


@dataclass 
class PriceData:
    """Data model for financial price/market data from various sources."""
    
    symbol: str
    price: Decimal
    timestamp: datetime
    volume: Optional[int] = None
    market: Optional[str] = None
    data_type: str = "current"  # current, historical, real_time
    currency: str = "USD"
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_percent_24h: Optional[float] = None
    unique_id: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if not isinstance(self.price, Decimal):
            raise TypeError("price must be Decimal object")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be datetime object")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume cannot be negative")