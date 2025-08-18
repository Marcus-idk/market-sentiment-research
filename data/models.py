from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse

def _valid_http_url(u: str) -> bool:
    p = urlparse(u.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)

@dataclass
class NewsItem:
    symbol: str
    url: str
    headline: str
    published: datetime
    source: str
    content: Optional[str] = None

    def __post_init__(self):
        self.symbol = self.symbol.strip()
        self.url = self.url.strip()
        self.headline = self.headline.strip()
        self.source = self.source.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if not self.headline: raise ValueError("headline cannot be empty")
        if not self.source: raise ValueError("source cannot be empty")
        if not _valid_http_url(self.url): raise ValueError("url must be http(s)")
        if self.published.tzinfo is None: self.published = self.published.replace(tzinfo=timezone.utc)

@dataclass
class PriceData:
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: Optional[int] = None
    is_extended: bool = False

    def __post_init__(self):
        self.symbol = self.symbol.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if self.timestamp.tzinfo is None: self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        if self.price < 0: raise ValueError("price must be >= 0")
        if self.volume is not None and self.volume < 0: raise ValueError("volume must be >= 0")
        self.is_extended = bool(self.is_extended)