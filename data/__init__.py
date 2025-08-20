# Data module for trading bot - clean exports
# Components will be added as they're implemented

# Core abstractions (available immediately)
from .base import DataSource, NewsDataSource, PriceDataSource

# Data models
from .models import NewsItem, PriceData, AnalysisResult, Holdings, Session, Stance, AnalysisType

# Storage operations
from .storage import (
    init_database, store_news_items, store_price_data, 
    get_news_since, get_price_data_since, upsert_analysis_result,
    upsert_holdings, get_all_holdings, get_analysis_results
)

__all__ = [
    'DataSource', 'NewsDataSource', 'PriceDataSource',
    'NewsItem', 'PriceData', 'AnalysisResult', 'Holdings', 
    'Session', 'Stance', 'AnalysisType',
    'init_database', 'store_news_items', 'store_price_data',
    'get_news_since', 'get_price_data_since', 'upsert_analysis_result',
    'upsert_holdings', 'get_all_holdings', 'get_analysis_results'
]