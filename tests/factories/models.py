"""Shared factories for building data model instances in tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from data.models import (
    AnalysisResult,
    AnalysisType,
    Holdings,
    NewsEntry,
    NewsItem,
    NewsType,
    PriceData,
    Session,
    Stance,
)

_DEFAULT_TIME = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)


def make_news_item(
    *,
    url: str = "https://example.com/news",
    headline: str = "Headline",
    source: str = "UnitTest",
    published: datetime | None = None,
    news_type: NewsType = NewsType.COMPANY_SPECIFIC,
    content: str | None = None,
) -> NewsItem:
    published_at = published or _DEFAULT_TIME
    return NewsItem(
        url=url,
        headline=headline,
        source=source,
        published=published_at,
        news_type=news_type,
        content=content,
    )


def make_news_entry(
    *,
    symbol: str = "AAPL",
    url: str = "https://example.com/news",
    headline: str = "Headline",
    source: str = "UnitTest",
    published: datetime | None = None,
    news_type: NewsType = NewsType.COMPANY_SPECIFIC,
    content: str | None = None,
    is_important: bool | None = None,
) -> NewsEntry:
    article = make_news_item(
        url=url,
        headline=headline,
        source=source,
        published=published,
        news_type=news_type,
        content=content,
    )
    return NewsEntry(article=article, symbol=symbol, is_important=is_important)


def make_price_data(
    *,
    symbol: str = "AAPL",
    timestamp: datetime | None = None,
    price: Decimal = Decimal("150.00"),
    volume: int | None = None,
    session: Session = Session.REG,
) -> PriceData:
    timestamp_dt = timestamp or _DEFAULT_TIME
    return PriceData(
        symbol=symbol,
        timestamp=timestamp_dt,
        price=price,
        volume=volume,
        session=session,
    )


def make_analysis_result(
    *,
    symbol: str = "AAPL",
    analysis_type: AnalysisType = AnalysisType.NEWS_ANALYSIS,
    model_name: str = "test-model",
    stance: Stance = Stance.NEUTRAL,
    confidence_score: float = 0.5,
    last_updated: datetime | None = None,
    created_at: datetime | None = None,
    result_json: str = '{"status": "ok"}',
) -> AnalysisResult:
    return AnalysisResult(
        symbol=symbol,
        analysis_type=analysis_type,
        model_name=model_name,
        stance=stance,
        confidence_score=confidence_score,
        last_updated=last_updated or _DEFAULT_TIME,
        created_at=created_at or _DEFAULT_TIME,
        result_json=result_json,
    )


def make_holdings(
    *,
    symbol: str = "AAPL",
    quantity: Decimal = Decimal("100.0"),
    break_even_price: Decimal = Decimal("150.00"),
    total_cost: Decimal = Decimal("15000.00"),
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    notes: str | None = None,
) -> Holdings:
    return Holdings(
        symbol=symbol,
        quantity=quantity,
        break_even_price=break_even_price,
        total_cost=total_cost,
        created_at=created_at or _DEFAULT_TIME,
        updated_at=updated_at or _DEFAULT_TIME,
        notes=notes,
    )
