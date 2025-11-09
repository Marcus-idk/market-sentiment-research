"""Edge-case coverage for data.storage.storage_core."""

import sqlite3

import pytest

from data.storage import connect, finalize_database, init_database
from data.storage.db_context import _cursor_context
from data.storage.storage_core import _check_json1_support


class FakeConnection:
    """Simple sqlite3 connection stub for PRAGMA tests."""

    def __init__(self, *, fail_foreign: bool = False, fail_busy: bool = False) -> None:
        self.fail_foreign = fail_foreign
        self.fail_busy = fail_busy

    def execute(self, sql: str):
        if sql == "PRAGMA foreign_keys = ON" and self.fail_foreign:
            raise sqlite3.Error("foreign key pragma failed")
        if sql == "PRAGMA busy_timeout = 5000" and self.fail_busy:
            raise sqlite3.Error("busy timeout pragma failed")
        return None


def test_connect_logs_when_foreign_keys_pragma_fails(monkeypatch, caplog):
    caplog.set_level("WARNING")
    monkeypatch.setattr(
        sqlite3, "connect", lambda *args, **kwargs: FakeConnection(fail_foreign=True)
    )

    conn = connect("ignored.db")

    assert isinstance(conn, FakeConnection)
    assert "Failed to enable SQLite foreign_keys pragma" in caplog.text


def test_connect_logs_when_busy_timeout_pragma_fails(monkeypatch, caplog):
    caplog.set_level("WARNING")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: FakeConnection(fail_busy=True))

    conn = connect("ignored.db")

    assert isinstance(conn, FakeConnection)
    assert "Failed to apply SQLite busy_timeout pragma" in caplog.text


def test_check_json1_support_returns_false_when_extension_missing(caplog):
    class JsonLessConnection:
        def execute(self, _sql: str):
            raise sqlite3.OperationalError("no such function: json_valid")

    caplog.set_level("DEBUG")

    from typing import cast

    assert _check_json1_support(cast(sqlite3.Connection, JsonLessConnection())) is False
    assert "SQLite JSON1 extension not available" in caplog.text


def test_init_database_raises_when_json1_missing(monkeypatch, tmp_path):
    class ContextlessConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: ContextlessConnection())
    monkeypatch.setattr("data.storage.storage_core._check_json1_support", lambda conn: False)

    with pytest.raises(RuntimeError, match="SQLite JSON1 extension required"):
        init_database(tmp_path / "fake.db")


def test_finalize_database_raises_when_path_missing(tmp_path):
    missing = tmp_path / "nope.db"

    with pytest.raises(FileNotFoundError, match="Database not found"):
        finalize_database(str(missing))


def test_finalize_database_switches_to_delete_mode(temp_db):
    finalize_database(temp_db)

    with _cursor_context(temp_db, commit=False) as cursor:
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

    assert mode.lower() == "delete"
