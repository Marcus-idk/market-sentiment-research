"""
CRUD operations for trading bot data storage.
Handles storing, querying, and updating news, prices, analysis, and holdings.
"""

from datetime import UTC, datetime

from data.models import AnalysisResult, Holdings, NewsEntry, NewsSymbol, NewsType, PriceData
from data.storage.db_context import _cursor_context
from data.storage.storage_utils import (
    _datetime_to_iso,
    _decimal_to_text,
    _normalize_url,
    _row_to_analysis_result,
    _row_to_holdings,
    _row_to_news_entry,
    _row_to_news_symbol,
    _row_to_price_data,
)


def store_news_items(db_path: str, items: list[NewsEntry]) -> None:
    """
    Store news entries using normalized URLs and many-to-many symbol links.
    Splits each NewsEntry into a NewsItem + NewsSymbol pair.
    """
    if not items:
        return

    with _cursor_context(db_path) as cursor:
        for item in items:
            article = item.article
            normalized_url = _normalize_url(article.url)

            try:
                if isinstance(article.news_type, NewsType):
                    news_type_value = article.news_type.value
                else:
                    news_type_value = NewsType(str(article.news_type)).value
            except Exception as exc:
                raise ValueError(
                    f"Invalid news_type for NewsItem; expected NewsType or valid string: {exc}"
                ) from exc

            cursor.execute(
                """
                INSERT OR IGNORE INTO news_items
                (url, headline, content, published_iso, source, news_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    normalized_url,
                    article.headline,
                    article.content,
                    _datetime_to_iso(article.published),
                    article.source,
                    news_type_value,
                ),
            )

            importance = None if item.is_important is None else int(item.is_important)
            cursor.execute(
                """
                INSERT INTO news_symbols
                (url, symbol, is_important)
                VALUES (?, ?, ?)
                ON CONFLICT(url, symbol) DO UPDATE SET
                    is_important = excluded.is_important
            """,
                (
                    normalized_url,
                    item.symbol,
                    importance,
                ),
            )


def store_price_data(db_path: str, items: list[PriceData]) -> None:
    """
    Store price data in the database with type conversions.
    Uses INSERT OR IGNORE to handle duplicates gracefully.
    """
    if not items:
        return

    with _cursor_context(db_path) as cursor:
        for item in items:
            cursor.execute(
                """
                INSERT OR IGNORE INTO price_data
                (symbol, timestamp_iso, price, volume, session)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    item.symbol,
                    _datetime_to_iso(item.timestamp),
                    _decimal_to_text(item.price),
                    item.volume,
                    item.session.value,
                ),
            )


def get_news_since(db_path: str, timestamp: datetime) -> list[NewsEntry]:
    """
    Retrieve news entries since the given timestamp.
    Returns NewsEntry domain objects with datetime fields in UTC.
    """
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute(
            """
            SELECT
                ni.url,
                ni.headline,
                ni.content,
                ni.published_iso,
                ni.source,
                ni.news_type,
                ns.symbol,
                ns.is_important
            FROM news_items AS ni
            JOIN news_symbols AS ns ON ns.url = ni.url
            WHERE ni.published_iso >= ?
            ORDER BY ni.published_iso ASC, ns.symbol ASC
        """,
            (_datetime_to_iso(timestamp),),
        )

        return [_row_to_news_entry(dict(row)) for row in cursor.fetchall()]


def get_news_symbols(db_path: str, symbol: str | None = None) -> list[NewsSymbol]:
    """Retrieve stored news symbol links, optionally filtered by symbol."""
    with _cursor_context(db_path, commit=False) as cursor:
        if symbol:
            symbol_key = symbol.strip().upper()
            cursor.execute(
                """
                SELECT url, symbol, is_important
                FROM news_symbols
                WHERE symbol = ?
                ORDER BY url ASC
            """,
                (symbol_key,),
            )
        else:
            cursor.execute(
                """
                SELECT url, symbol, is_important
                FROM news_symbols
                ORDER BY symbol ASC, url ASC
            """
            )

        return [_row_to_news_symbol(dict(row)) for row in cursor.fetchall()]


def get_price_data_since(db_path: str, timestamp: datetime) -> list[PriceData]:
    """
    Retrieve price data since the given timestamp.
    Returns PriceData model objects with datetime fields in UTC.
    """
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute(
            """
            SELECT symbol, timestamp_iso, price, volume, session
            FROM price_data
            WHERE timestamp_iso >= ?
            ORDER BY timestamp_iso ASC
        """,
            (_datetime_to_iso(timestamp),),
        )

        return [_row_to_price_data(dict(row)) for row in cursor.fetchall()]


def get_all_holdings(db_path: str) -> list[Holdings]:
    """
    Retrieve all current holdings.
    Returns Holdings model objects with datetime fields in UTC.
    """
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute("""
            SELECT symbol, quantity, break_even_price, total_cost, notes,
                   created_at_iso, updated_at_iso
            FROM holdings
            ORDER BY symbol ASC
        """)

        return [_row_to_holdings(dict(row)) for row in cursor.fetchall()]


def get_analysis_results(db_path: str, symbol: str | None = None) -> list[AnalysisResult]:
    """
    Retrieve analysis results, optionally filtered by symbol.
    Returns AnalysisResult model objects with datetime fields in UTC.
    """
    with _cursor_context(db_path, commit=False) as cursor:
        if symbol:
            cursor.execute(
                """
                SELECT symbol, analysis_type, model_name, stance, confidence_score,
                       last_updated_iso, result_json, created_at_iso
                FROM analysis_results
                WHERE symbol = ?
                ORDER BY analysis_type ASC
            """,
                (symbol,),
            )
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
    with _cursor_context(db_path) as cursor:
        # Set created_at if not provided
        created_at_iso = (
            _datetime_to_iso(result.created_at)
            if result.created_at
            else _datetime_to_iso(datetime.now(UTC))
        )

        cursor.execute(
            """
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
        """,
            (
                result.symbol,
                result.analysis_type.value,
                result.model_name,
                result.stance.value,
                result.confidence_score,
                _datetime_to_iso(result.last_updated),
                result.result_json,
                created_at_iso,
            ),
        )


def upsert_holdings(db_path: str, holdings: Holdings) -> None:
    """
    Insert or update holdings using ON CONFLICT.
    Updates existing position or creates new one.
    """
    with _cursor_context(db_path) as cursor:
        # Set timestamps if not provided
        now_iso = _datetime_to_iso(datetime.now(UTC))
        created_at_iso = _datetime_to_iso(holdings.created_at) if holdings.created_at else now_iso
        updated_at_iso = _datetime_to_iso(holdings.updated_at) if holdings.updated_at else now_iso

        cursor.execute(
            """
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
        """,
            (
                holdings.symbol,
                _decimal_to_text(holdings.quantity),
                _decimal_to_text(holdings.break_even_price),
                _decimal_to_text(holdings.total_cost),
                holdings.notes,
                created_at_iso,
                updated_at_iso,
            ),
        )
