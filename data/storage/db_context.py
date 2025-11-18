"""Internal database context manager utilities for SQLite work."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from data.storage.storage_core import connect


@contextmanager
def _cursor_context(db_path: str, *, commit: bool = True) -> Iterator[sqlite3.Cursor]:
    """Context manager for SQLite cursors with auto-commit/rollback."""
    conn = connect(db_path)
    conn.row_factory = sqlite3.Row  # Always enable dict-like row access

    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    except BaseException:
        conn.rollback()  # Rollback on ANY exception including Ctrl+C
        raise
    finally:
        conn.close()
