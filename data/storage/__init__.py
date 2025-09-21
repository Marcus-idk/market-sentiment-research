"""
Trading bot data storage package.
Re-exports all storage functions to maintain backward compatibility.
"""

# Core database functions
from .storage_core import (
    connect,
    init_database,
    finalize_database,
    _check_json1_support
)

# CRUD operations
from .storage_crud import (
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
from .storage_batch import (
    get_last_seen,
    set_last_seen,
    get_last_news_time,
    set_last_news_time,
    get_news_before,
    get_prices_before,
    commit_llm_batch
)

# Utility functions (exported for tests and internal use)
from .storage_utils import (
    _normalize_url,
    _datetime_to_iso,
    _iso_to_datetime,
    _decimal_to_text,
    _row_to_news_item,
    _row_to_news_label,
    _row_to_price_data,
    _row_to_analysis_result,
    _row_to_holdings
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
    'get_news_before',
    'get_prices_before',
    'commit_llm_batch',

    # Private functions (for tests)
    '_normalize_url',
    '_datetime_to_iso',
    '_iso_to_datetime',
    '_decimal_to_text',
    '_row_to_news_item',
    '_row_to_news_label',
    '_row_to_price_data',
    '_row_to_analysis_result',
    '_row_to_holdings',
    '_check_json1_support',
]