"""
SQLite storage operations for trading bot data.
Handles database initialization, CRUD operations, and type conversions.
"""

import sqlite3
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Union, Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from .models import NewsItem, PriceData, AnalysisResult, Holdings


def _normalize_url(url: str) -> str:
    """
    Normalize URL by stripping tracking parameters for cross-provider deduplication.
    Removes: utm_source, utm_medium, utm_campaign, ref, fbclid, etc.
    """
    parsed = urlparse(url)
    
    # Common tracking parameters to remove
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'ref', 'fbclid', 'gclid', 'msclkid', 'campaign'
    }
    
    # Parse query parameters and filter out tracking ones
    query_params = parse_qs(parsed.query)
    clean_params = {k: v for k, v in query_params.items() 
                   if k.lower() not in tracking_params}
    
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
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _decimal_to_text(decimal_val: Decimal) -> str:
    """Convert Decimal to TEXT format for exact precision storage."""
    return str(decimal_val)


def _check_json1_support(conn: sqlite3.Connection) -> bool:
    """Check if SQLite JSON1 extension is available."""
    try:
        conn.execute("SELECT json_valid('{}')")
        return True
    except sqlite3.OperationalError:
        return False


def init_database(db_path: str) -> None:
    """
    Initialize SQLite database by executing schema.sql.
    Creates all tables and sets performance optimizations.
    Requires SQLite JSON1 extension for data integrity.
    """
    # Check JSON1 support at startup - fail fast if missing
    with sqlite3.connect(":memory:") as conn:
        if not _check_json1_support(conn):
            raise RuntimeError(
                "SQLite JSON1 extension required but not available. "
                "Please use Python 3.8+ or install pysqlite3-binary. "
                "To install: pip install pysqlite3-binary"
            )
    
    # Read schema file
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Execute schema
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def finalize_database(db_path: str) -> None:
    """
    Finalize database for archiving/committing by merging WAL and removing sidecar files.
    
    This function should be called before:
    - Committing the database to Git
    - Copying/archiving the database file
    - Any operation that needs all data in the main .db file
    
    It performs:
    1. PRAGMA wal_checkpoint(TRUNCATE) - Forces all WAL data into main database
    2. PRAGMA journal_mode=DELETE - Switches from WAL mode to remove sidecar files
    
    After this, only the .db file contains all data (no .db-wal or .db-shm needed).
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    with sqlite3.connect(db_path) as conn:
        # Force all WAL transactions into main database
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # Switch to DELETE mode to remove sidecar files
        conn.execute("PRAGMA journal_mode=DELETE")
        
        conn.commit()


def store_news_items(db_path: str, items: List[NewsItem]) -> None:
    """
    Store news items in the database with URL normalization.
    Uses INSERT OR IGNORE to handle duplicates gracefully.
    """
    if not items:
        return
    
    with sqlite3.connect(db_path) as conn:
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


def store_price_data(db_path: str, items: List[PriceData]) -> None:
    """
    Store price data in the database with type conversions.
    Uses INSERT OR IGNORE to handle duplicates gracefully.
    """
    if not items:
        return
    
    with sqlite3.connect(db_path) as conn:
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


def get_news_since(db_path: str, timestamp: datetime) -> List[Dict]:
    """
    Retrieve news items since the given timestamp.
    Returns raw dictionaries for flexible processing.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, url, headline, content, published_iso, source, created_at_iso
            FROM news_items 
            WHERE published_iso >= ?
            ORDER BY published_iso ASC
        """, (_datetime_to_iso(timestamp),))
        
        return [dict(row) for row in cursor.fetchall()]


def get_price_data_since(db_path: str, timestamp: datetime) -> List[Dict]:
    """
    Retrieve price data since the given timestamp.
    Returns raw dictionaries for flexible processing.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, timestamp_iso, price, volume, session, created_at_iso
            FROM price_data 
            WHERE timestamp_iso >= ?
            ORDER BY timestamp_iso ASC
        """, (_datetime_to_iso(timestamp),))
        
        return [dict(row) for row in cursor.fetchall()]


def upsert_analysis_result(db_path: str, result: AnalysisResult) -> None:
    """
    Insert or update analysis result using ON CONFLICT.
    Updates existing analysis or creates new one.
    """
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db_path) as conn:
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


def get_all_holdings(db_path: str) -> List[Dict]:
    """
    Retrieve all current holdings.
    Returns raw dictionaries for flexible processing.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, quantity, break_even_price, total_cost, notes,
                   created_at_iso, updated_at_iso
            FROM holdings 
            ORDER BY symbol ASC
        """)
        
        return [dict(row) for row in cursor.fetchall()]


def get_analysis_results(db_path: str, symbol: str = None) -> List[Dict]:
    """
    Retrieve analysis results, optionally filtered by symbol.
    Returns raw dictionaries for flexible processing.
    """
    with sqlite3.connect(db_path) as conn:
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
        
        return [dict(row) for row in cursor.fetchall()]


# ===============================
# LAST_SEEN TABLE OPERATIONS
# ===============================

def get_last_seen(db_path: str, key: str) -> Optional[str]:
    """
    Get a value from last_seen table. Returns None if key doesn't exist.
    
    Args:
        db_path: Path to SQLite database
        key: The key to look up
        
    Returns:
        The stored value or None if key doesn't exist
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
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
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO last_seen (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()


def get_last_news_time(db_path: str) -> Optional[datetime]:
    """
    Get the timestamp of the most recent news we've fetched (news_since_iso).
    
    Returns:
        datetime object in UTC or None if not set
    """
    value = get_last_seen(db_path, 'news_since_iso')
    if value:
        # Parse ISO string to datetime
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return None


def set_last_news_time(db_path: str, timestamp: datetime) -> None:
    """
    Update the last fetched news timestamp (news_since_iso).
    
    Args:
        timestamp: The timestamp to store (will be converted to UTC)
    """
    iso_str = _datetime_to_iso(timestamp)
    set_last_seen(db_path, 'news_since_iso', iso_str)

def get_news_before(db_path: str, cutoff: datetime) -> List[Dict]:
    """
    Get news items created at or before the cutoff for LLM processing.
    
    Args:
        cutoff: Include items with created_at_iso <= this timestamp
        
    Returns:
        List of news items as dictionaries
    """
    iso_cutoff = _datetime_to_iso(cutoff)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, url, headline, content, published_iso, source, created_at_iso
            FROM news_items 
            WHERE created_at_iso <= ?
            ORDER BY created_at_iso ASC, symbol ASC
        """, (iso_cutoff,))
        
        return [dict(row) for row in cursor.fetchall()]


def get_prices_before(db_path: str, cutoff: datetime) -> List[Dict]:
    """
    Get price data created at or before the cutoff for LLM processing.
    
    Args:
        cutoff: Include items with created_at_iso <= this timestamp
        
    Returns:
        List of price data as dictionaries
    """
    iso_cutoff = _datetime_to_iso(cutoff)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, timestamp_iso, price, volume, session, created_at_iso
            FROM price_data 
            WHERE created_at_iso <= ?
            ORDER BY created_at_iso ASC, symbol ASC
        """, (iso_cutoff,))
        
        return [dict(row) for row in cursor.fetchall()]


def commit_llm_batch(db_path: str, cutoff: datetime) -> Dict[str, int]:
    """
    Atomically record the LLM cutoff and prune processed raw data.

    This performs, in a single transaction:
      1) Set `last_seen['llm_last_run_iso'] = cutoff`
      2) DELETE from `news_items` and `price_data` where `created_at_iso <= cutoff`

    Args:
        db_path: Path to the SQLite database
        cutoff: The snapshot cutoff used for the LLM batch

    Returns:
        Dict with counts of deleted rows: {"news_deleted": int, "prices_deleted": int}
    """
    iso_cutoff = _datetime_to_iso(cutoff)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 1) Persist the cutoff watermark
        cursor.execute(
            "INSERT OR REPLACE INTO last_seen (key, value) VALUES ('llm_last_run_iso', ?)",
            (iso_cutoff,)
        )

        # 2) Prune items processed in this batch
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

        conn.commit()

    return {"news_deleted": news_deleted, "prices_deleted": prices_deleted}
