from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
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

class NewsLabelType(Enum):
    COMPANY = "Company"
    PEOPLE = "People"
    MARKET_WITH_MENTION = "MarketWithMention"

class Urgency(Enum):
    URGENT = "URGENT"
    NOT_URGENT = "NOT_URGENT"

def _valid_http_url(u: str) -> bool:
    p = urlparse(u.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


def _normalize_to_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime without altering the wall time.

    - If `dt` is naive, attach UTC tzinfo.
    - If `dt` is aware, convert to UTC via `astimezone`.

    This centralizes the UTC normalization used by model `__post_init__` methods.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@dataclass
class NewsItem:
    symbol: str
    url: str
    headline: str
    published: datetime
    source: str
    content: str | None = None

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        self.url = self.url.strip()
        self.headline = self.headline.strip()
        self.source = self.source.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if not self.headline: raise ValueError("headline cannot be empty")
        if not self.source: raise ValueError("source cannot be empty")
        if not _valid_http_url(self.url): raise ValueError("url must be http(s)")
        self.published = _normalize_to_utc(self.published)

@dataclass
class NewsLabel:
    symbol: str
    url: str
    label: NewsLabelType
    created_at: datetime | None = None

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        self.url = self.url.strip()
        if isinstance(self.label, str):
            try:
                self.label = NewsLabelType(self.label)
            except ValueError as exc:
                raise ValueError(f"label must be a NewsLabelType value: {self.label}") from exc
        if not isinstance(self.label, NewsLabelType):
            raise ValueError("label must be a NewsLabelType enum value")
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if not _valid_http_url(self.url):
            raise ValueError("url must be http(s)")
        if self.created_at is not None:
            self.created_at = _normalize_to_utc(self.created_at)

@dataclass
class PriceData:
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: int | None = None
    session: Session = Session.REG

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        self.timestamp = _normalize_to_utc(self.timestamp)
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
    created_at: datetime | None = None

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
        self.last_updated = _normalize_to_utc(self.last_updated)
        if self.created_at is not None:
            self.created_at = _normalize_to_utc(self.created_at)

@dataclass
class Holdings:
    symbol: str
    quantity: Decimal
    break_even_price: Decimal
    total_cost: Decimal
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if self.notes is not None:
            self.notes = self.notes.strip()
        if not self.symbol: raise ValueError("symbol cannot be empty")
        if self.quantity <= 0: raise ValueError("quantity must be > 0")
        if self.break_even_price <= 0: raise ValueError("break_even_price must be > 0")
        if self.total_cost <= 0: raise ValueError("total_cost must be > 0")
        if self.created_at is not None:
            self.created_at = _normalize_to_utc(self.created_at)
        if self.updated_at is not None:
            self.updated_at = _normalize_to_utc(self.updated_at)
