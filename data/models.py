from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from urllib.parse import urlparse
import json

class Session(Enum):
    REG = "REG"       # Regular trading session (09:30–16:00 ET)
    PRE = "PRE"       # Pre-market session (04:00–09:30 ET)
    POST = "POST"     # After-hours session (16:00–20:00 ET)
    CLOSED = "CLOSED" # Overnight/closed (20:00–04:00 ET)

class Stance(Enum):
    BULL = "BULL"    # Bullish/positive stance
    BEAR = "BEAR"    # Bearish/negative stance
    NEUTRAL = "NEUTRAL"  # Neutral stance

class AnalysisType(Enum):
    NEWS_ANALYSIS = "news_analysis"        # News Analyst LLM
    SENTIMENT_ANALYSIS = "sentiment_analysis"  # Sentiment Analyst LLM
    SEC_FILINGS = "sec_filings"           # SEC Filings Analyst LLM
    HEAD_TRADER = "head_trader"           # Head Trader LLM

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
        self.symbol = self.symbol.strip().upper()
        self.url = self.url.strip()
        self.headline = self.headline.strip()
        self.source = self.source.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if not self.headline: raise ValueError("headline cannot be empty")
        if not self.source: raise ValueError("source cannot be empty")
        if not _valid_http_url(self.url): raise ValueError("url must be http(s)")
        if self.published.tzinfo is None: 
            self.published = self.published.replace(tzinfo=timezone.utc)
        else:
            self.published = self.published.astimezone(timezone.utc)

@dataclass
class PriceData:
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: Optional[int] = None
    session: Session = Session.REG

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if self.timestamp.tzinfo is None: 
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        else:
            self.timestamp = self.timestamp.astimezone(timezone.utc)
        if self.price <= 0: raise ValueError("price must be > 0")
        if self.volume is not None and self.volume < 0: raise ValueError("volume must be >= 0")
        if not isinstance(self.session, Session): 
            raise ValueError("session must be a Session enum value")

@dataclass
class AnalysisResult:
    symbol: str
    analysis_type: AnalysisType
    model_name: str
    stance: Stance
    confidence_score: float
    last_updated: datetime
    result_json: str
    created_at: Optional[datetime] = None

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        self.model_name = self.model_name.strip()
        self.result_json = self.result_json.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if not self.model_name: raise ValueError("model_name cannot be empty")
        if not self.result_json: raise ValueError("result_json cannot be empty")
        try:
            parsed_json = json.loads(self.result_json)
            if not isinstance(parsed_json, dict):
                raise ValueError("result_json must be a JSON object")
        except json.JSONDecodeError as e:
            raise ValueError(f"result_json must be valid JSON: {e}")
        if not isinstance(self.analysis_type, AnalysisType):
            raise ValueError("analysis_type must be an AnalysisType enum value")
        if not isinstance(self.stance, Stance):
            raise ValueError("stance must be a Stance enum value")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        if self.last_updated.tzinfo is None: 
            self.last_updated = self.last_updated.replace(tzinfo=timezone.utc)
        else:
            self.last_updated = self.last_updated.astimezone(timezone.utc)
        if self.created_at is not None:
            if self.created_at.tzinfo is None:
                self.created_at = self.created_at.replace(tzinfo=timezone.utc)
            else:
                self.created_at = self.created_at.astimezone(timezone.utc)

@dataclass
class Holdings:
    symbol: str
    quantity: Decimal
    break_even_price: Decimal
    total_cost: Decimal
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if self.notes is not None:
            self.notes = self.notes.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if self.quantity <= 0: raise ValueError("quantity must be > 0")
        if self.break_even_price <= 0: raise ValueError("break_even_price must be > 0")
        if self.total_cost <= 0: raise ValueError("total_cost must be > 0")
        if self.created_at is not None:
            if self.created_at.tzinfo is None:
                self.created_at = self.created_at.replace(tzinfo=timezone.utc)
            else:
                self.created_at = self.created_at.astimezone(timezone.utc)
        if self.updated_at is not None:
            if self.updated_at.tzinfo is None:
                self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
            else:
                self.updated_at = self.updated_at.astimezone(timezone.utc)
