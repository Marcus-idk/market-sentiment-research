"""
CRUD operations for trading bot data storage.
Handles storing, querying, and updating news, prices, analysis, and holdings.
"""

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from data.models import (
    NewsItem, PriceData, AnalysisResult, Holdings, NewsLabel,
    Session, Stance, AnalysisType, NewsLabelType
)
from .storage_core import connect
from .storage_utils import (
    _normalize_url, _datetime_to_iso, _decimal_to_text,
    _row_to_news_item, _row_to_news_label, _row_to_price_data,
    _row_to_analysis_result, _row_to_holdings
)


def store_news_items(db_path: str, items: List[NewsItem]) -> None:
    """
    Store news items in the database with URL normalization.
    Uses INSERT OR IGNORE to handle duplicates gracefully.
    """
    if not items:
        return

    with connect(db_path) as conn:
        cursor = conn.cursor()

        for item in items:
            # Normalize URL for deduplication
            normalized_url = _normalize_url(item.url)

            cursor.execute("""
                INSERT OR IGNORE INTO news_items
                (symbol, url, headline, content, published_iso, source)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item.symbol,
                normalized_url,
                item.headline,
                item.content,
                _datetime_to_iso(item.published),
                item.source
            ))

        conn.commit()


def store_news_labels(db_path: str, labels: List[NewsLabel]) -> None:
    """
    Insert or update news classification labels for stored news items.
    """
    if not labels:
        return

    with connect(db_path) as conn:
        cursor = conn.cursor()

        for label in labels:
            normalized_url = _normalize_url(label.url)
            created_at_iso = _datetime_to_iso(label.created_at) if label.created_at else _datetime_to_iso(datetime.now(timezone.utc))
            cursor.execute("""
                INSERT INTO news_labels (symbol, url, label, created_at_iso)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, url) DO UPDATE SET
                    label = excluded.label,
                    created_at_iso = excluded.created_at_iso
            """, (
                label.symbol,
                normalized_url,
                label.label.value,
                created_at_iso
            ))

        conn.commit()


def store_price_data(db_path: str, items: List[PriceData]) -> None:
    """
    Store price data in the database with type conversions.
    Uses INSERT OR IGNORE to handle duplicates gracefully.
    """
    if not items:
        return

    with connect(db_path) as conn:
        cursor = conn.cursor()

        for item in items:
            cursor.execute("""
                INSERT OR IGNORE INTO price_data
                (symbol, timestamp_iso, price, volume, session)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item.symbol,
                _datetime_to_iso(item.timestamp),
                _decimal_to_text(item.price),
                item.volume,
                item.session.value
            ))

        conn.commit()

def get_news_since(db_path: str, timestamp: datetime) -> List[NewsItem]:
    """
    Retrieve news items since the given timestamp.
    Returns NewsItem model objects with datetime fields in UTC.
    """
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symbol, url, headline, content, published_iso, source, created_at_iso
            FROM news_items
            WHERE published_iso >= ?
            ORDER BY published_iso ASC
        """, (_datetime_to_iso(timestamp),))

        return [_row_to_news_item(dict(row)) for row in cursor.fetchall()]


def get_news_labels(db_path: str, symbol: Optional[str] = None) -> List[NewsLabel]:
    """Retrieve stored news labels, optionally filtered by symbol."""
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if symbol:
            symbol_key = symbol.strip().upper()
            cursor.execute("""
                SELECT symbol, url, label, created_at_iso
                FROM news_labels
                WHERE symbol = ?
                ORDER BY created_at_iso ASC, url ASC
            """, (symbol_key,))
        else:
            cursor.execute("""
                SELECT symbol, url, label, created_at_iso
                FROM news_labels
                ORDER BY symbol ASC, created_at_iso ASC, url ASC
            """)

        return [_row_to_news_label(dict(row)) for row in cursor.fetchall()]


def get_price_data_since(db_path: str, timestamp: datetime) -> List[PriceData]:
    """
    Retrieve price data since the given timestamp.
    Returns PriceData model objects with datetime fields in UTC.
    """
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symbol, timestamp_iso, price, volume, session, created_at_iso
            FROM price_data
            WHERE timestamp_iso >= ?
            ORDER BY timestamp_iso ASC
        """, (_datetime_to_iso(timestamp),))

        return [_row_to_price_data(dict(row)) for row in cursor.fetchall()]


def get_all_holdings(db_path: str) -> List[Holdings]:
    """
    Retrieve all current holdings.
    Returns Holdings model objects with datetime fields in UTC.
    """
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symbol, quantity, break_even_price, total_cost, notes,
                   created_at_iso, updated_at_iso
            FROM holdings
            ORDER BY symbol ASC
        """)

        return [_row_to_holdings(dict(row)) for row in cursor.fetchall()]


def get_analysis_results(db_path: str, symbol: str = None) -> List[AnalysisResult]:
    """
    Retrieve analysis results, optionally filtered by symbol.
    Returns AnalysisResult model objects with datetime fields in UTC.
    """
    with connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if symbol:
            cursor.execute("""
                SELECT symbol, analysis_type, model_name, stance, confidence_score,
                       last_updated_iso, result_json, created_at_iso
                FROM analysis_results
                WHERE symbol = ?
                ORDER BY analysis_type ASC
            """, (symbol,))
        else:
            cursor.execute("""
                SELECT symbol, analysis_type, model_name, stance, confidence_score,
                       last_updated_iso, result_json, created_at_iso
                FROM analysis_results
                ORDER BY symbol ASC, analysis_type ASC
            """)

        return [_row_to_analysis_result(dict(row)) for row in cursor.fetchall()]

def upsert_analysis_result(db_path: str, result: AnalysisResult) -> None:
    """
    Insert or update analysis result using ON CONFLICT.
    Updates existing analysis or creates new one.
    """
    with connect(db_path) as conn:
        cursor = conn.cursor()

        # Set created_at if not provided
        created_at_iso = (_datetime_to_iso(result.created_at)
                         if result.created_at
                         else _datetime_to_iso(datetime.now(timezone.utc)))

        cursor.execute("""
            INSERT INTO analysis_results
            (symbol, analysis_type, model_name, stance, confidence_score,
             last_updated_iso, result_json, created_at_iso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, analysis_type) DO UPDATE SET
                model_name = excluded.model_name,
                stance = excluded.stance,
                confidence_score = excluded.confidence_score,
                last_updated_iso = excluded.last_updated_iso,
                result_json = excluded.result_json
        """, (
            result.symbol,
            result.analysis_type.value,
            result.model_name,
            result.stance.value,
            result.confidence_score,
            _datetime_to_iso(result.last_updated),
            result.result_json,
            created_at_iso
        ))

        conn.commit()


def upsert_holdings(db_path: str, holdings: Holdings) -> None:
    """
    Insert or update holdings using ON CONFLICT.
    Updates existing position or creates new one.
    """
    with connect(db_path) as conn:
        cursor = conn.cursor()

        # Set timestamps if not provided
        now_iso = _datetime_to_iso(datetime.now(timezone.utc))
        created_at_iso = (_datetime_to_iso(holdings.created_at)
                         if holdings.created_at
                         else now_iso)
        updated_at_iso = (_datetime_to_iso(holdings.updated_at)
                         if holdings.updated_at
                         else now_iso)

        cursor.execute("""
            INSERT INTO holdings
            (symbol, quantity, break_even_price, total_cost, notes,
             created_at_iso, updated_at_iso)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                quantity = excluded.quantity,
                break_even_price = excluded.break_even_price,
                total_cost = excluded.total_cost,
                notes = excluded.notes,
                updated_at_iso = excluded.updated_at_iso
        """, (
            holdings.symbol,
            _decimal_to_text(holdings.quantity),
            _decimal_to_text(holdings.break_even_price),
            _decimal_to_text(holdings.total_cost),
            holdings.notes,
            created_at_iso,
            updated_at_iso
        ))

        conn.commit()