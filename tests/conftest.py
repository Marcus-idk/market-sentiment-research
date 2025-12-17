"""Project-wide pytest fixtures and utilities."""

from __future__ import annotations

import gc
import logging
import os
import sqlite3
import tempfile
from contextlib import closing
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from data.storage import connect, init_database

logger = logging.getLogger(__name__)


def cleanup_sqlite_artifacts(db_path: str):
    """Clean up temporary SQLite database and related WAL/SHM artifacts."""
    if not os.path.exists(db_path):
        return

    gc.collect()

    # Removes connection, memory and files
    try:
        # Use closing() to ensure connection is properly closed
        with closing(connect(db_path)) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # Merge WAL→main DB
            conn.execute("PRAGMA journal_mode=DELETE")  # Exit WAL mode (key for Windows)
            conn.commit()
    except sqlite3.Error as exc:
        logger.warning("Failed to checkpoint SQLite WAL for %s: %s", db_path, exc)

    gc.collect()

    # Fallback File Removal
    for suffix in ("-wal", "-shm", ""):
        path = db_path + suffix
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except PermissionError:
            gc.collect()
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except PermissionError as exc:
                logger.warning(
                    "Failed to remove SQLite artifact %s after GC (file may still be locked): %s",
                    path,
                    exc,
                )


@pytest.fixture
def temp_db_path():
    """Yield path to a temporary SQLite database and clean it up afterwards."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # get rid of fd (a id number for the path), we don't need
    yield db_path
    cleanup_sqlite_artifacts(db_path)


@pytest.fixture
def temp_db(temp_db_path):
    """Initialize a temporary TradingBot database and yield its path."""
    init_database(temp_db_path)
    yield temp_db_path


@pytest.fixture
def mock_http_client(monkeypatch):
    """Provide a factory that returns a mocked httpx.AsyncClient."""

    def _create_mock_client(mock_get_func):
        # Create the fake client
        mock_client = Mock()
        mock_client.get = AsyncMock(side_effect=mock_get_func)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Replace httpx.AsyncClient with our fake (accept arbitrary init kwargs)
        monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: mock_client)
        return mock_client

    return _create_mock_client
