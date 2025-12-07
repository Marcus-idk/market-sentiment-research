"""Edge-case coverage for data.storage.storage_core."""

import sqlite3
from typing import cast

import pytest

from data.storage import connect, finalize_database, init_database
from data.storage.db_context import _cursor_context
from data.storage.storage_core import _check_json1_support


class FakeConnection:
    def __init__(
        self,
        *,
        fail_foreign: bool = False,
        fail_busy: bool = False,
        fail_wal: bool = False,
        fail_sync: bool = False,
    ) -> None:
        self.fail_foreign = fail_foreign
        self.fail_busy = fail_busy
        self.fail_wal = fail_wal
        self.fail_sync = fail_sync

    def execute(self, sql: str):
        if sql == "PRAGMA foreign_keys = ON" and self.fail_foreign:
            raise sqlite3.Error("foreign key pragma failed")
        if sql == "PRAGMA busy_timeout = 5000" and self.fail_busy:
            raise sqlite3.Error("busy timeout pragma failed")
        if sql == "PRAGMA journal_mode = WAL" and self.fail_wal:
            raise sqlite3.Error("wal pragma failed")
        if sql == "PRAGMA synchronous = NORMAL" and self.fail_sync:
            raise sqlite3.Error("sync pragma failed")
        return None


def test_connect_logs_when_foreign_keys_pragma_fails(monkeypatch, caplog):
    """Test connect logs when foreign keys pragma fails."""
    caplog.set_level("WARNING")
    monkeypatch.setattr(
        sqlite3, "connect", lambda *args, **kwargs: FakeConnection(fail_foreign=True)
    )

    conn = connect("ignored.db")

    assert isinstance(conn, FakeConnection)
    assert "Failed to enable SQLite foreign_keys pragma" in caplog.text


def test_connect_logs_when_busy_timeout_pragma_fails(monkeypatch, caplog):
    """Test connect logs when busy timeout pragma fails."""
    caplog.set_level("WARNING")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: FakeConnection(fail_busy=True))

    conn = connect("ignored.db")

    assert isinstance(conn, FakeConnection)
    assert "Failed to apply SQLite busy_timeout pragma" in caplog.text


def test_connect_logs_when_wal_pragma_fails(monkeypatch, caplog):
    """Test connect logs when WAL pragma fails."""
    caplog.set_level("WARNING")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: FakeConnection(fail_wal=True))

    conn = connect("ignored.db")

    assert isinstance(conn, FakeConnection)
    assert "Failed to set SQLite journal_mode=WAL" in caplog.text


def test_connect_logs_when_sync_pragma_fails(monkeypatch, caplog):
    """Test connect logs when synchronous pragma fails."""
    caplog.set_level("WARNING")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: FakeConnection(fail_sync=True))

    conn = connect("ignored.db")

    assert isinstance(conn, FakeConnection)
    assert "Failed to set SQLite synchronous=NORMAL" in caplog.text


def test_connect_sets_wal_and_synchronous(tmp_path):
    """Successful connect enforces WAL and synchronous=NORMAL."""
    db_path = tmp_path / "wal.db"

    conn = connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = str(cursor.fetchone()[0]).lower()
        cursor.execute("PRAGMA synchronous")
        sync = str(cursor.fetchone()[0]).lower()
    finally:
        conn.close()

    assert mode == "wal"
    assert sync in {"normal", "1"}  # some SQLite builds return numeric code for NORMAL


def test_check_json1_support_returns_false_when_extension_missing(caplog):
    """Test check json1 support returns false when extension missing."""

    class JsonLessConnection:
        def execute(self, _sql: str):
            raise sqlite3.OperationalError("no such function: json_valid")

    caplog.set_level("DEBUG")

    assert _check_json1_support(cast(sqlite3.Connection, JsonLessConnection())) is False
    assert "SQLite JSON1 extension not available" in caplog.text


def test_init_database_raises_when_json1_missing(monkeypatch, tmp_path):
    """Test init database raises when json1 missing."""

    class ContextlessConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def close(self):
            pass

    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: ContextlessConnection())
    monkeypatch.setattr("data.storage.storage_core._check_json1_support", lambda conn: False)

    with pytest.raises(RuntimeError, match="SQLite JSON1 extension required"):
        init_database(tmp_path / "fake.db")


def test_finalize_database_raises_when_path_missing(tmp_path):
    """Test finalize database raises when path missing."""
    missing = tmp_path / "nope.db"

    with pytest.raises(FileNotFoundError, match="Database not found"):
        finalize_database(str(missing))


def test_finalize_database_switches_to_delete_mode(temp_db):
    """Test finalize database switches to delete mode."""
    finalize_database(temp_db)

    # Check raw mode without re-enabling WAL
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

    assert mode.lower() == "delete"

    # Normal connections should restore WAL
    with _cursor_context(temp_db, commit=False) as cursor:
        cursor.execute("PRAGMA journal_mode")
        mode_wal = cursor.fetchone()[0]

    assert mode_wal.lower() == "wal"


def test_finalize_database_runs_checkpoint(monkeypatch, tmp_path):
    """Finalize issues synchronous=FULL, checkpoint, and delete mode."""
    db_path = tmp_path / "finalize.db"
    db_path.touch()
    executed: list[str] = []

    class FinalizeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql: str):
            executed.append(sql)

        def commit(self):
            executed.append("COMMIT")

        def close(self):
            executed.append("CLOSE")

    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: FinalizeConnection())

    finalize_database(str(db_path))

    assert "PRAGMA synchronous = FULL" in executed
    assert "PRAGMA wal_checkpoint(TRUNCATE)" in executed
    assert "PRAGMA journal_mode=DELETE" in executed
    assert "COMMIT" in executed
