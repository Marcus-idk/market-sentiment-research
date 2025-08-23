"""
Shared pytest fixtures and utilities for all tests.
This file is automatically discovered by pytest and its contents are available to all test files.
"""

import gc
import os
import sqlite3


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
        with sqlite3.connect(uri, uri=True) as conn:
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