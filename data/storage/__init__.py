"""Public facade for trading bot data storage helpers."""

# Core database functions
from data.storage.storage_core import (
    connect,
    init_database,
    finalize_database,
)

# CRUD operations
from data.storage.storage_crud import (
    store_news_items,
    store_news_labels,
    store_price_data,
    get_news_since,
    get_news_labels,
    get_price_data_since,
    get_all_holdings,
    get_analysis_results,
    upsert_analysis_result,
    upsert_holdings
)

# Batch operations and watermarks
from data.storage.storage_batch import (
    get_last_seen,
    set_last_seen,
    get_last_news_time,
    set_last_news_time,
    get_last_macro_min_id,
    set_last_macro_min_id,
    get_news_before,
    get_prices_before,
    commit_llm_batch
)

# All public functions (for backward compatibility)
__all__ = [
    # Core database
    'connect',
    'init_database',
    'finalize_database',

    # CRUD operations
    'store_news_items',
    'store_news_labels',
    'store_price_data',
    'get_news_since',
    'get_news_labels',
    'get_price_data_since',
    'get_all_holdings',
    'get_analysis_results',
    'upsert_analysis_result',
    'upsert_holdings',

    # Batch and watermarks
    'get_last_seen',
    'set_last_seen',
    'get_last_news_time',
    'set_last_news_time',
    'get_last_macro_min_id',
    'set_last_macro_min_id',
    'get_news_before',
    'get_prices_before',
    'commit_llm_batch',
]