import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from urllib.parse import urlparse

from utils.datetime_utils import normalize_to_utc


class Session(Enum):
    REG = "REG"  # Regular trading session (09:30–16:00 ET / 22:30–05:00 SGT)
    PRE = "PRE"  # Pre-market session (04:00–09:30 ET / 17:00–22:30 SGT)
    POST = "POST"  # After-hours session (16:00–20:00 ET / 05:00–09:00 SGT)
    CLOSED = "CLOSED"  # Overnight/closed (20:00–04:00 ET / 09:00–17:00 SGT)


class Stance(Enum):
    BULL = "BULL"  # Up
    BEAR = "BEAR"  # Down
    NEUTRAL = "NEUTRAL"  # Sideways


class AnalysisType(Enum):
    NEWS_ANALYSIS = "news_analysis"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    SEC_FILINGS = "sec_filings"
    HEAD_TRADER = "head_trader"


class Urgency(Enum):
    URGENT = "URGENT"
    NOT_URGENT = "NOT_URGENT"


class NewsType(Enum):
    MACRO = "macro"
    COMPANY_SPECIFIC = "company_specific"


def _valid_http_url(u: str) -> bool:
    """Check if url is a real host."""
    p = urlparse(u.strip())
    # Require http/https scheme and a non-empty netloc like "example.com"
    return p.scheme in ("http", "https") and bool(p.netloc)


@dataclass
class NewsItem:
    url: str
    headline: str
    published: datetime
    source: str
    news_type: NewsType | str
    content: str | None = None

    def __post_init__(self) -> None:
        self.url = self.url.strip()
        self.headline = self.headline.strip()
        self.source = self.source.strip()
        if not self.headline:
            raise ValueError("headline cannot be empty")
        if not self.source:
            raise ValueError("source cannot be empty")
        if not _valid_http_url(self.url):
            raise ValueError("url must be http(s)")
        if isinstance(self.news_type, str):
            self.news_type = NewsType(self.news_type)
        if not isinstance(self.news_type, NewsType):
            raise ValueError("news_type must be a NewsType enum value")
        self.published = normalize_to_utc(self.published)


@dataclass
class NewsSymbol:
    url: str
    symbol: str
    is_important: bool | None = None

    def __post_init__(self) -> None:
        self.url = self.url.strip()
        self.symbol = self.symbol.strip().upper()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if not _valid_http_url(self.url):
            raise ValueError("url must be http(s)")
        if self.is_important is not None and not isinstance(self.is_important, bool):
            raise ValueError("is_important must be True, False, or None")


@dataclass
class NewsEntry:
    article: NewsItem
    symbol: str
    is_important: bool | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if self.is_important is not None and not isinstance(self.is_important, bool):
            raise ValueError("is_important must be True, False, or None")

    @property
    def url(self) -> str:
        return self.article.url

    @property
    def headline(self) -> str:
        return self.article.headline

    @property
    def published(self) -> datetime:
        return self.article.published

    @property
    def source(self) -> str:
        return self.article.source

    @property
    def content(self) -> str | None:
        return self.article.content

    @property
    def news_type(self) -> NewsType:
        nt = self.article.news_type
        return nt if isinstance(nt, NewsType) else NewsType(nt)


@dataclass
class PriceData:
    symbol: str
    timestamp: datetime
    price: Decimal
    volume: int | None = None
    session: Session = Session.REG

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        self.timestamp = normalize_to_utc(self.timestamp)
        if self.price <= 0:
            raise ValueError("price must be > 0")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume must be >= 0")
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

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.model_name = self.model_name.strip()
        self.result_json = self.result_json.strip()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if not self.model_name:
            raise ValueError("model_name cannot be empty")
        if not self.result_json:
            raise ValueError("result_json cannot be empty")
        try:
            parsed_json = json.loads(self.result_json)
            if not isinstance(parsed_json, dict):
                raise ValueError("result_json must be a JSON object")
        except json.JSONDecodeError as exc:
            raise ValueError(f"result_json must be valid JSON: {exc}") from exc
        if not isinstance(self.analysis_type, AnalysisType):
            raise ValueError("analysis_type must be an AnalysisType enum value")
        if not isinstance(self.stance, Stance):
            raise ValueError("stance must be a Stance enum value")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        self.last_updated = normalize_to_utc(self.last_updated)
        if self.created_at is not None:
            self.created_at = normalize_to_utc(self.created_at)


@dataclass
class Holdings:
    symbol: str
    quantity: Decimal
    break_even_price: Decimal
    total_cost: Decimal
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        if self.notes is not None:
            self.notes = self.notes.strip()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")
        if self.break_even_price <= 0:
            raise ValueError("break_even_price must be > 0")
        if self.total_cost <= 0:
            raise ValueError("total_cost must be > 0")
        if self.created_at is not None:
            self.created_at = normalize_to_utc(self.created_at)
        if self.updated_at is not None:
            self.updated_at = normalize_to_utc(self.updated_at)
