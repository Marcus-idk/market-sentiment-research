"""
Finnhub API provider implementations for news and price data.

This module provides:
- FinnhubClient: Minimal HTTP wrapper with retry logic
- FinnhubNewsProvider: Company news fetching via /company-news endpoint  
- FinnhubPriceProvider: Real-time quotes via /quote endpoint
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from config.providers.finnhub import FinnhubSettings
from data.base import NewsDataSource, PriceDataSource, DataSourceError
from data.models import NewsItem, PriceData, Session
from utils.http import get_json_with_retry
from utils.market_sessions import classify_us_session

class FinnhubClient:
    """
    Minimal async HTTP client wrapper for Finnhub API calls.
    
    Handles authentication, timeouts, and basic retry logic for 429/5xx errors.
    """
    
    def __init__(self, settings: FinnhubSettings):
        """
        Initialize client with settings.
        
        Args:
            settings: Finnhub configuration (API key, timeouts, retries)
        """
        self.settings = settings
    
    
    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Make authenticated GET request with retry logic using short-lived session.
        
        Args:
            path: API endpoint path (e.g., '/company-news')
            params: Optional query parameters
            
        Returns:
            Parsed JSON response (dict or list)
            
        Raises:
            DataSourceError: On authentication, client, or persistent server errors
        """
        # Build URL and merge params with API token
        url = f"{self.settings.base_url}{path}"
        params = {**(params or {}), 'token': self.settings.api_key}
        
        # Use centralized HTTP retry helper
        return await get_json_with_retry(
            url,
            params=params,
            timeout=self.settings.retry_config.timeout_seconds,
            max_retries=self.settings.retry_config.max_retries,
            base=self.settings.retry_config.base,
            mult=self.settings.retry_config.mult,
            jitter=self.settings.retry_config.jitter,
        )
    
    async def validate_connection(self) -> bool:
        """
        Test connection by fetching quote for SPY (always available).
        Centralized validation logic for all Finnhub providers.
        
        Returns:
            True if connection successful, False otherwise (never raises)
        """
        try:
            await self.get('/quote', {'symbol': 'SPY'})
            return True
        except Exception:
            return False


class FinnhubNewsProvider(NewsDataSource):
    """
    Fetches company news from Finnhub's /company-news endpoint.
    
    Maps news articles to NewsItem models with proper UTC timestamps and validation.
    Supports incremental fetching based on publication dates.
    """
    
    def __init__(self, settings: FinnhubSettings, symbols: List[str], source_name: str = "Finnhub"):
        """
        Initialize news provider with settings and symbol list.
        
        Args:
            settings: Finnhub API configuration
            symbols: List of stock symbols to fetch news for (e.g., ['AAPL', 'TSLA'])
            source_name: Data source identifier for logging/debugging
        """
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)
        
    async def validate_connection(self) -> bool:
        """
        Validate connection via the centralized client method.
        
        Returns:
            True if connection successful, False otherwise (never raises)
        """
        return await self.client.validate_connection()
    
    async def fetch_incremental(self, since: Optional[datetime] = None) -> List[NewsItem]:
        """
        Fetch company news articles since the given timestamp.
        
        Args:
            since: Only fetch articles published after this UTC datetime.
                  If None, fetch articles from 2 days ago to avoid missing items.
                  
        Returns:
            List of NewsItem objects with valid headlines, URLs, and UTC timestamps
        """
        if not self.symbols:
            return []
        
        # Determine date range for API calls
        now_utc = datetime.now(timezone.utc)
        
        # Calculate effective since time with buffer
        if since is not None:
            # Apply 2-minute buffer to catch late-arriving articles
            buffer_time = since - timedelta(minutes=2)
            from_date = buffer_time.date()
        else:
            # Default: fetch last 2 days to avoid missing late postings
            from_date = (now_utc - timedelta(days=2)).date()
            buffer_time = None
        
        to_date = now_utc.date()
        
        news_items = []
        
        for symbol in self.symbols:
            try:
                # Call /company-news endpoint
                params = {
                    'symbol': symbol,
                    'from': from_date.strftime('%Y-%m-%d'),
                    'to': to_date.strftime('%Y-%m-%d')
                }
                
                articles = await self.client.get('/company-news', params)
                
                if not isinstance(articles, list):
                    continue
                
                # Process each article
                for article in articles:
                    try:
                        # Pass buffer_time for filtering, not original since
                        news_item = self._parse_article(article, symbol, buffer_time if since else None)
                        if news_item:
                            news_items.append(news_item)                                
                    except Exception:
                        # Skip invalid articles, continue with others
                        continue
                        
            except Exception:
                # Skip symbol on error, continue with remaining symbols
                continue
        
        return news_items
    
    def _parse_article(self, article: Dict[str, Any], symbol: str, 
                      buffer_time: Optional[datetime]) -> Optional[NewsItem]:
        """
        Parse Finnhub article JSON into NewsItem model.
        
        Args:
            article: Raw article data from Finnhub API
            symbol: Stock symbol this article is associated with
            buffer_time: Filter out articles published at or before this time (includes buffer)
            
        Returns:
            NewsItem if valid, None if article should be skipped
        """
        # Validate required fields
        headline = article.get('headline', '').strip()
        url = article.get('url', '').strip()
        datetime_epoch = article.get('datetime', 0)
        
        if not headline or not url or datetime_epoch <= 0:
            return None
        
        
        # Convert epoch timestamp to UTC datetime
        try:
            published = datetime.fromtimestamp(datetime_epoch, tz=timezone.utc)
        except (ValueError, OSError):
            return None
        
        # Filter by buffer_time (exclusive to avoid duplicates)
        if buffer_time and published <= buffer_time:
            return None
        
        # Extract other fields with defaults
        source = article.get('source', '').strip() or 'Finnhub'
        summary = article.get('summary', '').strip()
        content = summary if summary else None
        
        try:
            return NewsItem(
                symbol=symbol,
                url=url,
                headline=headline,
                published=published,
                source=source,
                content=content
            )
        except ValueError:
            # NewsItem validation failed
            return None
    


class FinnhubPriceProvider(PriceDataSource):
    """
    Fetches real-time stock quotes from Finnhub's /quote endpoint.
    
    Maps quote data to PriceData models with proper decimal precision and UTC timestamps.
    Each fetch returns current prices for all configured symbols.
    """
    
    def __init__(self, settings: FinnhubSettings, symbols: List[str], source_name: str = "Finnhub"):
        """
        Initialize price provider with settings and symbol list.
        
        Args:
            settings: Finnhub API configuration
            symbols: List of stock symbols to fetch quotes for (e.g., ['AAPL', 'TSLA'])
            source_name: Data source identifier for logging/debugging
        """
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)
    
    async def validate_connection(self) -> bool:
        """
        Validate connection via the centralized client method.
        
        Returns:
            True if connection successful, False otherwise (never raises)
        """
        return await self.client.validate_connection()
    
    async def fetch_incremental(self, since: Optional[datetime] = None) -> List[PriceData]:
        """
        Fetch current stock quotes for all symbols.
        
        Args:
            since: Ignored for quotes (each fetch gets current price)
            
        Returns:
            List of PriceData objects with current prices and UTC timestamps
        """
        if not self.symbols:
            return []
        
        price_data = []
        
        for symbol in self.symbols:
            try:
                # Call /quote endpoint
                quote = await self.client.get('/quote', {'symbol': symbol})
                
                if not isinstance(quote, dict):
                    continue
                
                # Parse quote data
                price_item = self._parse_quote(quote, symbol)
                if price_item:
                    price_data.append(price_item)
                    
            except Exception:
                # Skip symbol on error, continue with remaining symbols
                continue
        
        return price_data
    
    def _parse_quote(self, quote: Dict[str, Any], symbol: str) -> Optional[PriceData]:
        """
        Parse Finnhub quote JSON into PriceData model.
        
        Args:
            quote: Raw quote data from Finnhub API
            symbol: Stock symbol for this quote
            
        Returns:
            PriceData if valid price available, None if quote should be skipped  
        """
        # Validate current price (required)
        current_price = quote.get('c', 0)
        if current_price <= 0:
            return None
        
        # Convert to Decimal for financial precision
        try:
            price = Decimal(str(current_price))
        except (ValueError, TypeError):
            return None
        
        # Extract timestamp (use quote timestamp if available and valid, otherwise use now)
        quote_timestamp = quote.get('t', 0)
        if quote_timestamp > 0:
            try:
                timestamp = datetime.fromtimestamp(quote_timestamp, tz=timezone.utc)
            except (ValueError, OSError):
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        
        try:
            return PriceData(
                symbol=symbol,
                timestamp=timestamp, 
                price=price,
                volume=None,  # Not provided by /quote endpoint
                session=classify_us_session(timestamp)  # Determine actual session based on ET
            )
        except ValueError:
            # PriceData validation failed
            return None
