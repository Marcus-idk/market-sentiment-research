"""
Shared pytest fixtures and utilities for all tests.
This file is automatically discovered by pytest and its contents are available to all test files.
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, AsyncMock
import httpx
from data.storage import init_database
from tests.fixtures.database import cleanup_sqlite_artifacts


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


# Make utilities available to all test files
__all__ = ['cleanup_sqlite_artifacts']