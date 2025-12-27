"""Utility helpers and type conversions for Market Sentiment Analyzer storage."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from data.models import (
    AnalysisResult,
    AnalysisType,
    Holdings,
    NewsEntry,
    NewsItem,
    NewsSymbol,
    PriceData,
    Session,
    SocialDiscussion,
    Stance,
)


def _normalize_url(url: str) -> str:
    """Normalize URL by stripping common tracking parameters."""
    parsed = urlparse(url)
    # Lowercase the hostname for consistent deduplication
    parsed = parsed._replace(netloc=parsed.netloc.lower())

    # Common tracking parameters to remove
    tracking_params = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "ref",
        "fbclid",
        "gclid",
        "msclkid",
        "campaign",
    }

    # Parse query parameters and filter out tracking ones
    query_params = parse_qs(parsed.query)
    clean_params = {k: v for k, v in query_params.items() if k.lower() not in tracking_params}

    # Reconstruct query string with proper encoding
    if clean_params:
        # Flatten and sort for canonical order across providers
        pairs = [(k, v) for k, vs in clean_params.items() for v in vs]
        pairs.sort()  # Ensures consistent ordering
        clean_query = urlencode(pairs, doseq=True)
    else:
        clean_query = ""

    # Reconstruct URL without tracking parameters
    clean_parsed = parsed._replace(query=clean_query)
    return urlunparse(clean_parsed)


def _datetime_to_iso(dt: datetime) -> str:
    """Convert datetime to UTC ISO string format expected by database."""
    # Guideline note: this is the central helper the codebase should use for ISO strings.
    # The normalization below intentionally handles the 'Z' suffix.
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_to_datetime(iso_str: str) -> datetime:
    """Convert ISO string from database to UTC datetime object."""
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


def _decimal_to_text(decimal_val: Decimal) -> str:
    """Convert Decimal to TEXT format for exact precision storage."""
    return str(decimal_val)


def _row_to_news_item(row: dict[str, Any]) -> NewsItem:
    """Convert database row to NewsItem model."""
    return NewsItem(
        url=row["url"],
        headline=row["headline"],
        content=row.get("content"),
        published=_iso_to_datetime(row["published_iso"]),
        source=row["source"],
        news_type=row["news_type"],
    )


def _row_to_news_symbol(row: dict[str, Any]) -> NewsSymbol:
    """Convert database row to NewsSymbol model."""
    is_important_value = row.get("is_important")
    is_important = None if is_important_value is None else bool(is_important_value)
    return NewsSymbol(
        url=row["url"],
        symbol=row["symbol"],
        is_important=is_important,
    )


def _row_to_news_entry(row: dict[str, Any]) -> NewsEntry:
    """Convert joined row to NewsEntry domain model."""
    article = _row_to_news_item(
        {
            "url": row["url"],
            "headline": row["headline"],
            "content": row.get("content"),
            "published_iso": row["published_iso"],
            "source": row["source"],
            "news_type": row["news_type"],
        }
    )
    is_important_value = row.get("is_important")
    is_important = None if is_important_value is None else bool(is_important_value)
    return NewsEntry(article=article, symbol=row["symbol"], is_important=is_important)


def _row_to_price_data(row: dict[str, Any]) -> PriceData:
    """Convert database row to PriceData model."""
    return PriceData(
        symbol=row["symbol"],
        timestamp=_iso_to_datetime(row["timestamp_iso"]),
        price=Decimal(row["price"]),
        volume=row.get("volume"),
        session=Session(row["session"]),
    )


def _row_to_analysis_result(row: dict[str, Any]) -> AnalysisResult:
    """Convert database row to AnalysisResult model."""
    created_at = None
    if "created_at_iso" in row and row["created_at_iso"]:
        created_at = _iso_to_datetime(row["created_at_iso"])

    return AnalysisResult(
        symbol=row["symbol"],
        analysis_type=AnalysisType(row["analysis_type"]),
        model_name=row["model_name"],
        stance=Stance(row["stance"]),
        confidence_score=float(row["confidence_score"]),
        last_updated=_iso_to_datetime(row["last_updated_iso"]),
        result_json=row["result_json"],
        created_at=created_at,
    )


def _row_to_holdings(row: dict[str, Any]) -> Holdings:
    """Convert database row to Holdings model."""
    created_at = None
    updated_at = None
    if "created_at_iso" in row and row["created_at_iso"]:
        created_at = _iso_to_datetime(row["created_at_iso"])
    if "updated_at_iso" in row and row["updated_at_iso"]:
        updated_at = _iso_to_datetime(row["updated_at_iso"])

    return Holdings(
        symbol=row["symbol"],
        quantity=Decimal(row["quantity"]),
        break_even_price=Decimal(row["break_even_price"]),
        total_cost=Decimal(row["total_cost"]),
        notes=row.get("notes"),
        created_at=created_at,
        updated_at=updated_at,
    )


def _row_to_social_discussion(row: dict[str, Any]) -> SocialDiscussion:
    """Convert database row to SocialDiscussion model."""
    return SocialDiscussion(
        source=row["source"],
        source_id=row["source_id"],
        symbol=row["symbol"],
        community=row["community"],
        title=row["title"],
        url=row["url"],
        content=row.get("content"),
        published=_iso_to_datetime(row["published_iso"]),
    )
