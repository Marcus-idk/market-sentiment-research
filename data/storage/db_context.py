"""Internal database context manager utilities for reducing boilerplate."""

from contextlib import contextmanager
from typing import Iterator
import sqlite3
from .storage_core import connect

@contextmanager
def _cursor_context(
    db_path: str,
    commit: bool = True
) -> Iterator[sqlite3.Cursor]:
    """
    Internal context manager for database operations with automatic cleanup.

    Args:
        db_path: Path to SQLite database
        commit: Whether to commit on success (default: True for writes)

    Yields:
        sqlite3.Cursor ready for operations

    Example (write):
        with _cursor_context(db_path) as cursor:
            cursor.execute("INSERT INTO...")

    Example (read):
        with _cursor_context(db_path, commit=False) as cursor:
            cursor.execute("SELECT...")
            return [dict(row) for row in cursor.fetchall()]
    """
    conn = connect(db_path)
    conn.row_factory = sqlite3.Row  # Always enable dict-like row access

    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    except BaseException:
        conn.rollback()    # Rollback on ANY exception including Ctrl+C
        raise
    finally:
        conn.close()
