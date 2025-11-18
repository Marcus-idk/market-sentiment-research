"""Public data models, providers, and storage helpers for the trading bot."""

# Core abstractions (available immediately)
from data.base import DataSource, DataSourceError, NewsDataSource, PriceDataSource

# Data models
from data.models import (
    AnalysisResult,
    AnalysisType,
    Holdings,
    NewsEntry,
    NewsItem,
    NewsSymbol,
    NewsType,
    PriceData,
    Session,
    Stance,
)

# Storage operations
from data.storage import (
    commit_llm_batch,
    connect,
    finalize_database,
    get_all_holdings,
    get_analysis_results,
    get_news_before,
    get_news_since,
    get_news_symbols,
    get_price_data_since,
    get_prices_before,
    init_database,
    store_news_items,
    store_price_data,
    upsert_analysis_result,
    upsert_holdings,
)

__all__ = [
    "DataSource",
    "NewsDataSource",
    "PriceDataSource",
    "DataSourceError",
    "NewsItem",
    "NewsEntry",
    "NewsSymbol",
    "NewsType",
    "PriceData",
    "AnalysisResult",
    "Holdings",
    "Session",
    "Stance",
    "AnalysisType",
    "init_database",
    "finalize_database",
    "store_news_items",
    "store_price_data",
    "get_news_since",
    "get_news_symbols",
    "get_price_data_since",
    "upsert_analysis_result",
    "upsert_holdings",
    "get_all_holdings",
    "get_analysis_results",
    "connect",
    "get_news_before",
    "get_prices_before",
    "commit_llm_batch",
]
