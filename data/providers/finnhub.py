"""
Finnhub API provider implementations for news and price data.

This module provides:
- FinnhubClient: Minimal HTTP wrapper with retry logic
- FinnhubNewsProvider: Company news fetching via /company-news endpoint  
- FinnhubPriceProvider: Real-time quotes via /quote endpoint
"""

import asyncio
import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import httpx

from config.providers.finnhub import FinnhubSettings
from data.base import NewsDataSource, PriceDataSource, DataSourceError
from data.models import NewsItem, PriceData, Session

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
        # Add authentication token to params
        if params is None:
            params = {}
        params['token'] = self.settings.api_key
        
        url = f"{self.settings.base_url}{path}"
        timeout = self.settings.timeout_seconds
        
        # Retry logic for 429/5xx with jittered backoff
        last_exception = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                # Run blocking httpx.get in a thread to keep async interface simple
                def _do_request():
                    resp = httpx.get(url, params=params, timeout=timeout)
                    return resp

                response = await asyncio.to_thread(_do_request)

                status = response.status_code

                # Auth errors - don't retry
                if status in (401, 403):
                    raise DataSourceError(f"Authentication failed (status {status})")

                # Client errors (except 429) - don't retry
                if 400 <= status < 500 and status != 429:
                    raise DataSourceError(f"Client error (status {status})")

                # Success
                if status == 200:
                    try:
                        return response.json()
                    except ValueError as e:
                        raise DataSourceError(f"Invalid JSON response: {e}")

                # Server errors (5xx) or rate limit (429) - retry with backoff
                if status >= 500 or status == 429:
                    if attempt < self.settings.max_retries:
                        # Exponential backoff with jitter: 0.25s, 0.5s, 1s + random jitter
                        base_delay = 0.25 * (2 ** attempt)
                        jitter = random.uniform(-0.1, 0.1)
                        delay = max(0.1, base_delay + jitter)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise DataSourceError(f"Server error after {self.settings.max_retries} retries (status {status})")

                # Unexpected status code
                raise DataSourceError(f"Unexpected HTTP status: {status}")

            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.settings.max_retries:
                    delay = 0.25 * (2 ** attempt) + random.uniform(-0.1, 0.1)
                    await asyncio.sleep(max(0.1, delay))
                    continue
        
        # All retries exhausted
        raise DataSourceError(f"Network error after {self.settings.max_retries} retries: {last_exception}")


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
        Test connection by fetching quote for SPY (always available).
        
        Returns:
            True if connection successful, False otherwise (never raises)
        """
        try:
            await self.client.get('/quote', {'symbol': 'SPY'})
            return True
        except Exception:
            return False
    
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
        if since is not None:
            # Use 1-day cushion to avoid missing items around day boundaries
            from_date = min(since.date(), (now_utc - timedelta(days=1)).date())
        else:
            # Default: fetch last 2 days to avoid missing late postings
            from_date = (now_utc - timedelta(days=2)).date()
        
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
                        news_item = self._parse_article(article, symbol, since)
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
                      since: Optional[datetime]) -> Optional[NewsItem]:
        """
        Parse Finnhub article JSON into NewsItem model.
        
        Args:
            article: Raw article data from Finnhub API
            symbol: Stock symbol this article is associated with
            since: Filter out articles published before this time
            
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
        
        # Filter by since timestamp (client-side filtering as API date ranges may be inclusive)
        if since and published <= since:
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
        Test connection by fetching quote for SPY (always available).
        
        Returns:
            True if connection successful, False otherwise (never raises)
        """
        try:
            await self.client.get('/quote', {'symbol': 'SPY'})
            return True
        except Exception:
            return False
    
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
                session=Session.REG  # Default to regular session for now
            )
        except ValueError:
            # PriceData validation failed
            return None
