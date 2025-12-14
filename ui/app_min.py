"""Minimal Streamlit UI for browsing the TradingBot database."""

import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from data.storage.db_context import _cursor_context


def _friendly_table_name(raw_name: str) -> str:
    """Return a human-friendly label for a table name."""
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", raw_name)
    cleaned = " ".join(cleaned.split())
    return cleaned.title() if cleaned else raw_name


def fetch_table_names(db_path: str) -> list[str]:
    """Return sorted SQLite table names for the given database path."""
    with _cursor_context(db_path, commit=False) as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        return [row["name"] for row in cursor.fetchall()]


def build_display_map(names: list[str]) -> dict[str, str]:
    """Build a display-label-to-table-name mapping for the sidebar."""
    display_to_table: dict[str, str] = {}
    for raw in names:
        label = _friendly_table_name(raw)
        if label in display_to_table:
            label = f"{label} ({raw})"
        display_to_table[label] = raw
    return display_to_table


st.set_page_config(page_title="TradingBot DB", layout="wide", initial_sidebar_state="expanded")

DB_PATH = os.getenv("DATABASE_PATH", "data/database/trading_bot.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
table_names = fetch_table_names(DB_PATH)

if not table_names:
    st.sidebar.info("No tables found in the database.")
    selected = None
else:
    display_to_table = build_display_map(table_names)
    selected_label = st.sidebar.radio("Tables", list(display_to_table), index=0)
    selected = display_to_table[selected_label]

st.header("TradingBot DB")

if selected:
    with _cursor_context(DB_PATH, commit=False) as cursor:
        # `selected` comes from `sqlite_master` via `fetch_table_names`, so it is trusted.
        cursor.execute(f"SELECT * FROM {selected} LIMIT 1000")
        rows = [dict(row) for row in cursor.fetchall()]
    st.dataframe(
        pd.DataFrame.from_records(rows),
        use_container_width=True,
        height=500,
    )
