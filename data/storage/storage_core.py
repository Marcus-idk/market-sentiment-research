"""
Database lifecycle and connection management for trading bot data.
Handles database initialization, connections, and finalization.
"""

import sqlite3
import os
from importlib.resources import files
import logging

logger = logging.getLogger(__name__)


def connect(db_path: str, **kwargs) -> sqlite3.Connection:
    """Open a SQLite connection with required PRAGMAs enabled.

    Important: SQLite foreign key enforcement is disabled by default and must
    be enabled per-connection. This helper ensures `PRAGMA foreign_keys = ON` is
    set for all callers in this module.
    """
    conn = sqlite3.connect(db_path, **kwargs)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as e:
        logger.warning(f"Failed to enable SQLite foreign_keys pragma: {e}")
    return conn


def _check_json1_support(conn: sqlite3.Connection) -> bool:
    """Check if SQLite JSON1 extension is available."""
    try:
        conn.execute("SELECT json_valid('{}')")
        return True
    except sqlite3.OperationalError as exc:
        logger.debug(f"SQLite JSON1 extension not available: {exc}")
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

    # Read schema file using importlib.resources (works in packages)
    schema_sql = files('data').joinpath('schema.sql').read_text()

    # Execute schema
    with connect(db_path) as conn:
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

    with connect(db_path) as conn:
        # Force all WAL transactions into main database
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        # Switch to DELETE mode to remove sidecar files
        conn.execute("PRAGMA journal_mode=DELETE")

        conn.commit()
