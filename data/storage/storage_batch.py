"""
Batch operations and watermark management for trading bot data.
Handles LLM processing batches and state tracking.
"""

import logging
import sqlite3
from datetime import datetime

from data.models import NewsItem, PriceData
from data.storage.storage_utils import _datetime_to_iso, _iso_to_datetime, _row_to_news_item, _row_to_price_data
from data.storage.db_context import _cursor_context


logger = logging.getLogger(__name__)


def get_last_seen(db_path: str, key: str) -> str | None:
    """
    Get a value from last_seen table. Returns None if key doesn't exist.

    Args:
        db_path: Path to SQLite database
        key: The key to look up

    Returns:
        The stored value or None if key doesn't exist
    """
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute("SELECT value FROM last_seen WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None


def set_last_seen(db_path: str, key: str, value: str) -> None:
    """
    Set a value in last_seen table (INSERT OR REPLACE).

    Args:
        db_path: Path to SQLite database
        key: The key to store
        value: The value to store
    """
    with _cursor_context(db_path) as cursor:
        cursor.execute(
            "INSERT OR REPLACE INTO last_seen (key, value) VALUES (?, ?)",
            (key, value)
        )


def get_last_news_time(db_path: str) -> datetime | None:
    """
    Get the timestamp of the most recent news we've fetched (news_since_iso).

    Returns:
        datetime object in UTC or None if not set
    """
    value = get_last_seen(db_path, 'news_since_iso')
    if value:
        # Parse ISO string to datetime
        return _iso_to_datetime(value)
    return None


def set_last_news_time(db_path: str, timestamp: datetime) -> None:
    """
    Update the last fetched news timestamp (news_since_iso).

    Args:
        timestamp: The timestamp to store (will be converted to UTC)
    """
    iso_str = _datetime_to_iso(timestamp)
    set_last_seen(db_path, 'news_since_iso', iso_str)


def get_last_macro_min_id(db_path: str) -> int | None:
    """
    Get the last seen macro news article ID (minId watermark).

    Returns:
        Integer ID or None if not set (first run)
    """
    value = get_last_seen(db_path, 'macro_news_min_id')
    if value:
        try:
            return int(value)
        except ValueError as exc:
            logger.warning(
                f"Invalid macro_news_min_id in database ('{value}'); treating as unset: {exc}"
            )
            return None
    return None


def set_last_macro_min_id(db_path: str, min_id: int) -> None:
    """
    Update the last seen macro news article ID (minId watermark).

    Args:
        min_id: The max article ID from this fetch (becomes next minId)
    """
    set_last_seen(db_path, 'macro_news_min_id', str(min_id))


def get_news_before(db_path: str, cutoff: datetime) -> list[NewsItem]:
    """
    Get news items created at or before the cutoff for LLM processing.

    Args:
        cutoff: Include items with created_at_iso <= this timestamp

    Returns:
        List of NewsItem model objects with datetime fields in UTC
    """
    iso_cutoff = _datetime_to_iso(cutoff)
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute("""
            SELECT symbol, url, headline, content, published_iso, source, created_at_iso
            FROM news_items
            WHERE created_at_iso <= ?
            ORDER BY created_at_iso ASC, symbol ASC
        """, (iso_cutoff,))

        return [_row_to_news_item(dict(row)) for row in cursor.fetchall()]


def get_prices_before(db_path: str, cutoff: datetime) -> list[PriceData]:
    """
    Get price data created at or before the cutoff for LLM processing.

    Args:
        cutoff: Include items with created_at_iso <= this timestamp

    Returns:
        List of PriceData model objects with datetime fields in UTC
    """
    iso_cutoff = _datetime_to_iso(cutoff)
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute("""
            SELECT symbol, timestamp_iso, price, volume, session, created_at_iso
            FROM price_data
            WHERE created_at_iso <= ?
            ORDER BY created_at_iso ASC, symbol ASC
        """, (iso_cutoff,))

        return [_row_to_price_data(dict(row)) for row in cursor.fetchall()]


def commit_llm_batch(db_path: str, cutoff: datetime) -> dict[str, int]:
    """
    Atomically record the LLM cutoff and prune processed raw data.

    This performs, in a single transaction:
      1) Set `last_seen['llm_last_run_iso'] = cutoff`
      2) DELETE from `news_labels`, `news_items`, and `price_data` where `created_at_iso <= cutoff`

    Args:
        db_path: Path to the SQLite database
        cutoff: The snapshot cutoff used for the LLM batch

    Returns:
        Dict with counts of deleted rows: {"labels_deleted": int, "news_deleted": int, "prices_deleted": int}
    """
    iso_cutoff = _datetime_to_iso(cutoff)
    with _cursor_context(db_path) as cursor:
        # 1) Persist the cutoff watermark
        cursor.execute(
            "INSERT OR REPLACE INTO last_seen (key, value) VALUES ('llm_last_run_iso', ?)",
            (iso_cutoff,)
        )

        # 2) Prune items processed in this batch
        cursor.execute("""
            DELETE FROM news_labels
            WHERE EXISTS (
                SELECT 1
                FROM news_items AS ni
                WHERE ni.symbol = news_labels.symbol
                  AND ni.url = news_labels.url
                  AND ni.created_at_iso <= ?
            )
        """, (iso_cutoff,))
        labels_deleted = cursor.rowcount

        cursor.execute(
            "DELETE FROM news_items WHERE created_at_iso <= ?",
            (iso_cutoff,)
        )
        news_deleted = cursor.rowcount

        cursor.execute(
            "DELETE FROM price_data WHERE created_at_iso <= ?",
            (iso_cutoff,)
        )
        prices_deleted = cursor.rowcount

    return {"labels_deleted": labels_deleted, "news_deleted": news_deleted, "prices_deleted": prices_deleted}
