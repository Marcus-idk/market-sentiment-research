# Data module for trading bot - clean exports
# Components will be added as they're implemented

# Core abstractions (available immediately)
from .base import DataSource

# Data models (to be implemented)
# from .models import NewsItem, PriceData

# Storage and utilities (to be implemented)  
# from .storage import DataStorage
# from .deduplication import DeduplicationTracker

__all__ = [
    'DataSource',
    # 'NewsItem', 'PriceData',
    # 'DataStorage', 'DeduplicationTracker'
]