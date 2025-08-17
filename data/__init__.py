# Data module for trading bot - clean exports
# Components will be added as they're implemented

# Core abstractions (available immediately)
from .base import DataSource, NewsDataSource, PriceDataSource

# Data models
from .models import NewsItem, PriceData

# Storage and utilities (to be implemented)  
# from .storage import DataStorage
# from .deduplication import DeduplicationTracker

__all__ = [
    'DataSource', 'NewsDataSource', 'PriceDataSource',
    'NewsItem', 'PriceData',
    # 'DataStorage', 'DeduplicationTracker'
]