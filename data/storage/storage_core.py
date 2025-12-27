"""Database lifecycle and connection management for Market Sentiment Analyzer data."""

import logging
import os
import sqlite3
from contextlib import closing
from importlib.resources import files

logger = logging.getLogger(__name__)


def connect(db_path: str, **kwargs) -> sqlite3.Connection:
    """Open a SQLite connection with required PRAGMAs enabled."""
    # Direct sqlite3.connect is allowed here: this helper is the sanctioned entry point
    # that applies required PRAGMAs before use elsewhere in the codebase.
    conn = sqlite3.connect(db_path, **kwargs)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as e:
        logger.warning("Failed to enable SQLite foreign_keys pragma: %s", e)

    try:
        conn.execute("PRAGMA busy_timeout = 5000")
    except sqlite3.Error as e:
        logger.warning("Failed to apply SQLite busy_timeout pragma: %s", e)

    # Enforce WAL mode and synch (synch changes per connection, resets to FULL on new)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error as e:
        logger.warning("Failed to set SQLite journal_mode=WAL: %s", e)

    try:
        conn.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.Error as e:
        logger.warning("Failed to set SQLite synchronous=NORMAL: %s", e)
    return conn


def _check_json1_support(conn: sqlite3.Connection) -> bool:
    """Check if SQLite JSON1 extension is available."""
    try:
        conn.execute("SELECT json_valid('{}')")
        return True
    except sqlite3.OperationalError as exc:
        logger.debug("SQLite JSON1 extension not available: %s", exc)
        return False


def init_database(db_path: str) -> None:
    """Initialize SQLite database, enforcing JSON1 support and schema."""
    # Check JSON1 support at startup - fail fast if missing
    # In-memory connection is acceptable for capability checks; no disk access occurs.
    # sqlite3 connection context managers don't close the connection, so wrap with closing
    with closing(sqlite3.connect(":memory:")) as conn:
        if not _check_json1_support(conn):
            raise RuntimeError(
                "SQLite JSON1 extension required but not available. "
                "Install a SQLite build with JSON1 support (e.g., the 'pysqlite3-binary' package) "
                "or use a Python distribution that bundles JSON1."
            )

    # Read schema file using importlib.resources (works in packages)
    schema_sql = files("data").joinpath("schema.sql").read_text()

    # Execute schema
    # Use closing to ensure the connection releases WAL locks on Windows.
    with closing(connect(db_path)) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def finalize_database(db_path: str) -> None:
    """Finalize database by checkpointing WAL and switching to DELETE mode."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Bypass connect() to avoid re-enabling WAL during maintenance.
    with closing(sqlite3.connect(db_path)) as conn:
        try:
            conn.execute("PRAGMA synchronous = FULL")
        except sqlite3.Error as e:
            logger.warning("Failed to set SQLite synchronous=FULL during finalize: %s", e)

        # Force all WAL transactions into main database
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        # Switch to DELETE mode to remove sidecar files
        conn.execute("PRAGMA journal_mode=DELETE")

        conn.commit()
