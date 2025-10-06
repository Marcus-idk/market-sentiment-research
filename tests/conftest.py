"""
Shared pytest fixtures and utilities for all tests.
This file is automatically discovered by pytest and its contents are available to all test files.
"""

import gc
import os
import sqlite3
import tempfile
import pytest
from unittest.mock import Mock, AsyncMock
import httpx
from data.storage import init_database, connect
from data.storage.db_context import _cursor_context


def cleanup_sqlite_artifacts(db_path: str) -> None:
    """
    Windows-safe SQLite cleanup for WAL databases. Solves Windows file locking issues.
    
    Key steps:
    1. Checkpoint WAL data back to main DB
    2. Switch from WAL→DELETE mode (releases Windows memory-mapped .shm files)
    3. Delete files in correct order: -wal, -shm, then main .db
    4. Best-effort only - never fail tests due to cleanup issues
    """
    if not os.path.exists(db_path):
        return
    
    gc.collect()
    
    try:
        uri = f"file:{db_path}?mode=rw"
        with connect(uri, uri=True) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # Merge WAL→main DB
            conn.execute("PRAGMA journal_mode=DELETE")       # Exit WAL mode (key for Windows)
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
    fd, db_path = tempfile.mkstemp(suffix='.db')
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
        
        # Replace httpx.AsyncClient with our fake
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)
        return mock_client
    
    return _create_mock_client