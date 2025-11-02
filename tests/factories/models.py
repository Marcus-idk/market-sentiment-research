"""Shared factories for building data model instances in tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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
    """Return a NewsItem with deterministic defaults."""
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
    """Return a NewsEntry wrapping a NewsItem with shared defaults."""
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
    price: Decimal | float | str = Decimal("150.00"),
    volume: int | None = None,
    session: Session = Session.REG,
) -> PriceData:
    """Return PriceData with consistent defaults and timezone handling."""
    price_decimal = price if isinstance(price, Decimal) else Decimal(str(price))
    timestamp_dt = timestamp or _DEFAULT_TIME
    return PriceData(
        symbol=symbol,
        timestamp=timestamp_dt,
        price=price_decimal,
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
    extras: dict[str, Any] | None = None,
) -> AnalysisResult:
    """Return an AnalysisResult with deterministic timestamps."""
    payload: dict[str, Any] = {
        "symbol": symbol,
        "analysis_type": analysis_type,
        "model_name": model_name,
        "stance": stance,
        "confidence_score": confidence_score,
        "last_updated": last_updated or _DEFAULT_TIME,
        "created_at": created_at or _DEFAULT_TIME,
        "result_json": result_json,
    }
    if extras:
        payload.update(extras)
    return AnalysisResult(**payload)


def make_holdings(
    *,
    symbol: str = "AAPL",
    quantity: Decimal | float | str = Decimal("100.0"),
    break_even_price: Decimal | float | str = Decimal("150.00"),
    total_cost: Decimal | float | str = Decimal("15000.00"),
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    notes: str | None = None,
) -> Holdings:
    """Return Holdings with optional notes and deterministic timestamps."""
    quantity_decimal = quantity if isinstance(quantity, Decimal) else Decimal(str(quantity))
    break_even_decimal = (
        break_even_price
        if isinstance(break_even_price, Decimal)
        else Decimal(str(break_even_price))
    )
    total_cost_decimal = total_cost if isinstance(total_cost, Decimal) else Decimal(str(total_cost))
    return Holdings(
        symbol=symbol,
        quantity=quantity_decimal,
        break_even_price=break_even_decimal,
        total_cost=total_cost_decimal,
        created_at=created_at or _DEFAULT_TIME,
        updated_at=updated_at or _DEFAULT_TIME,
        notes=notes,
    )
