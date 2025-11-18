"""Public facade for trading bot data storage helpers."""

from data.storage.storage_batch import (
    commit_llm_batch,
    get_news_before,
    get_prices_before,
)
from data.storage.storage_core import (
    connect,
    finalize_database,
    init_database,
)
from data.storage.storage_crud import (
    get_all_holdings,
    get_analysis_results,
    get_news_since,
    get_news_symbols,
    get_price_data_since,
    store_news_items,
    store_price_data,
    upsert_analysis_result,
    upsert_holdings,
)
from data.storage.storage_watermark import (
    get_last_seen_id,
    get_last_seen_timestamp,
    set_last_seen_id,
    set_last_seen_timestamp,
)

__all__ = [
    "connect",
    "init_database",
    "finalize_database",
    "store_news_items",
    "store_price_data",
    "get_news_since",
    "get_news_symbols",
    "get_price_data_since",
    "get_all_holdings",
    "get_analysis_results",
    "upsert_analysis_result",
    "upsert_holdings",
    "get_news_before",
    "get_prices_before",
    "commit_llm_batch",
    "get_last_seen_timestamp",
    "set_last_seen_timestamp",
    "get_last_seen_id",
    "set_last_seen_id",
]
