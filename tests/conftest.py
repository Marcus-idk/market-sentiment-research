"""Project-wide pytest fixtures and utilities."""

from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from data.storage import connect, init_database


def cleanup_sqlite_artifacts(db_path: str):
    """Windows-safe cleanup for SQLite WAL databases used in tests."""
    if not os.path.exists(db_path):
        return

    gc.collect()

    try:
        with connect(db_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # Merge WAL→main DB
            conn.execute("PRAGMA journal_mode=DELETE")  # Exit WAL mode (key for Windows)
            conn.commit()
    except sqlite3.Error:
        pass

    gc.collect()

    for suffix in ("-wal", "-shm", ""):
        try:
            os.remove(db_path + suffix)
        except FileNotFoundError:
            pass
        except PermissionError:
            gc.collect()
            try:
                os.remove(db_path + suffix)
            except (FileNotFoundError, PermissionError):
                pass


@pytest.fixture
def temp_db_path():
    """Provides temporary database file path with automatic cleanup"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield db_path
    cleanup_sqlite_artifacts(db_path)


@pytest.fixture
def temp_db(temp_db_path):
    """Provides initialized temporary database with automatic cleanup"""
    init_database(temp_db_path)
    return temp_db_path


@pytest.fixture
def mock_http_client(monkeypatch):
    """Fixture to create a mocked httpx.AsyncClient for testing HTTP calls"""

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
