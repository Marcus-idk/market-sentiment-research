"""
Finnhub API provider implementations for news and price data.

This module provides:
- FinnhubClient: Minimal HTTP wrapper with retry logic
- FinnhubNewsProvider: Company news fetching via /company-news endpoint
- FinnhubMacroNewsProvider: Market-wide news fetching via /news endpoint
- FinnhubPriceProvider: Real-time quotes via /quote endpoint
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from config.providers.finnhub import FinnhubSettings
from data.base import NewsDataSource, PriceDataSource, DataSourceError
from data.models import NewsItem, PriceData, Session
from utils.http import get_json_with_retry
from utils.market_sessions import classify_us_session
from utils.symbols import parse_symbols

logger = logging.getLogger(__name__)

class FinnhubClient:
    """
    Minimal async HTTP client wrapper for Finnhub API calls.
    
    Handles authentication, timeouts, and basic retry logic for 429/5xx errors.
    """
    
    def __init__(self, settings: FinnhubSettings) -> None:
        """
        Initialize client with settings.

        Args:
            settings: Finnhub configuration (API key, timeouts, retries)
        """
        self.settings = settings
    
    
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
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

    def __init__(self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub") -> None:
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
    
    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        min_id: int | None = None
    ) -> list[NewsItem]:
        """
        Fetch company news articles since the given timestamp.

        Args:
            since: Only fetch articles published after this UTC datetime.
                  If None, fetch articles from 2 days ago to avoid missing items.
            min_id: Ignored (used by ID-based providers, not date-based)

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
                    except Exception as e:
                        # Skip invalid articles, continue with others
                        logger.debug(f"Failed to parse company news article for {symbol}: {e}")
                        continue

            except Exception as e:
                # Skip symbol on error, continue with remaining symbols
                logger.warning(f"Company news fetch failed for {symbol}: {e}")
                continue
        
        return news_items
    
    def _parse_article(self, article: dict[str, Any], symbol: str,
                      buffer_time: datetime | None) -> NewsItem | None:
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
        except (ValueError, OSError) as e:
            logger.debug(f"Skipping company news article for {symbol} due to invalid epoch {datetime_epoch}: {e}")
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
        except ValueError as e:
            # NewsItem validation failed
            logger.debug(f"NewsItem validation failed for {symbol} (url={url}): {e}")
            return None
    


class FinnhubPriceProvider(PriceDataSource):
    """
    Fetches real-time stock quotes from Finnhub's /quote endpoint.
    
    Maps quote data to PriceData models with proper decimal precision and UTC timestamps.
    Each fetch returns current prices for all configured symbols.
    """
    
    def __init__(self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub") -> None:
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
    
    async def fetch_incremental(self, since: datetime | None = None) -> list[PriceData]:
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

            except Exception as e:
                # Skip symbol on error, continue with remaining symbols
                logger.warning(f"Price quote fetch failed for {symbol}: {e}")
                continue
        
        return price_data
    
    def _parse_quote(self, quote: dict[str, Any], symbol: str) -> PriceData | None:
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
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid quote price for {symbol}: {current_price!r} ({e}) - skipping")
            return None
        
        # Extract timestamp (use quote timestamp if available and valid, otherwise use now)
        quote_timestamp = quote.get('t', 0)
        if quote_timestamp > 0:
            try:
                timestamp = datetime.fromtimestamp(quote_timestamp, tz=timezone.utc)
            except (ValueError, OSError) as e:
                logger.debug(f"Invalid quote timestamp for {symbol}: {quote_timestamp!r} ({e}) - using now()")
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
        except ValueError as e:
            # PriceData validation failed
            logger.debug(f"PriceData validation failed for {symbol} (price={price}): {e}")
            return None


class FinnhubMacroNewsProvider(NewsDataSource):
    """
    Fetches market-wide macro news from Finnhub's /news endpoint.

    Uses category='general' for broad market news. Maps news articles to NewsItem
    models with symbol assignment based on the 'related' field (or "ALL" fallback).
    Supports incremental fetching based on publication dates.
    """

    def __init__(self, settings: FinnhubSettings, symbols: list[str], source_name: str = "Finnhub Macro") -> None:
        """
        Initialize macro news provider with settings and watchlist symbols.

        Args:
            settings: Finnhub API configuration
            symbols: List of stock symbols on watchlist for filtering (e.g., ['AAPL', 'TSLA'])
            source_name: Data source identifier for logging/debugging
        """
        super().__init__(source_name)
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.client = FinnhubClient(settings)
        self.last_fetched_max_id: int | None = None

    async def validate_connection(self) -> bool:
        """
        Validate connection via the centralized client method.

        Returns:
            True if connection successful, False otherwise (never raises)
        """
        return await self.client.validate_connection()

    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        min_id: int | None = None
    ) -> list[NewsItem]:
        """
        Fetch macro news articles using minId pagination.

        Args:
            since: Ignored (used by date-based providers, not ID-based).
                   Macro news (/news) is independent from company news (/company-news),
                   so the shared last_news_time watermark does not apply here.
            min_id: Fetch articles with ID > min_id (for incremental fetching).
                   If None, bootstrap mode (first run defaults to last 2 days).

        Returns:
            List of NewsItem objects with valid headlines, URLs, and UTC timestamps.
            Symbol is assigned from 'related' field or defaults to "ALL".

        Note:
            Watermark strategy: This provider relies exclusively on macro_news_min_id.
            Bootstrap always uses 2-day lookback regardless of `since` parameter.
            After bootstrap, incremental fetching is driven solely by minId.
        """
        now_utc = datetime.now(timezone.utc)

        # Bootstrap mode: always use 2-day lookback (ignore `since` parameter)
        # Macro news is independent from company news, so last_news_time doesn't apply
        if min_id is None:
            buffer_time = now_utc - timedelta(days=2)
        else:
            # Incremental mode: minId is primary anchor, no datetime buffer needed
            buffer_time = None

        news_items = []

        # Call /news endpoint with category=general for macro news
        params = {'category': 'general'}

        # Add minId for incremental fetching if available
        if min_id is not None:
            params['minId'] = min_id

        articles = await self.client.get('/news', params)

        if not isinstance(articles, list):
            self.last_fetched_max_id = None
            return []

        # Filter out duplicates defensively (articles with id <= min_id)
        if min_id is not None:
            filtered_articles = [
                a for a in articles
                if isinstance(a.get('id'), int) and a['id'] > min_id
            ]
            if len(filtered_articles) < len(articles):
                logger.debug(
                    f"Filtered {len(articles) - len(filtered_articles)} articles "
                    f"with id <= {min_id}"
                )
            articles = filtered_articles

        # Process each article (now returns list of NewsItems, one per watchlist symbol)
        for article in articles:
            try:
                # Pass buffer_time for filtering, not original since
                # _parse_article returns list[NewsItem] (empty if filtered/invalid)
                items = self._parse_article(article, buffer_time)
                news_items.extend(items)
            except Exception as e:
                # Skip invalid articles, continue with others
                logger.debug(f"Failed to parse article {article.get('id', 'unknown')}: {e}")
                continue

        # Track max article ID for next incremental fetch
        ids = [a['id'] for a in articles if isinstance(a.get('id'), int) and a['id'] > 0]
        self.last_fetched_max_id = max(ids) if ids else None

        return news_items

    def _parse_article(self, article: dict[str, Any],
                      buffer_time: datetime | None) -> list[NewsItem]:
        """
        Parse Finnhub macro news article JSON into NewsItem models.

        Creates one NewsItem per watchlist symbol mentioned in the article's
        'related' field, or a single ALL item if no watchlist symbols found.

        Args:
            article: Raw article data from Finnhub API
            buffer_time: Filter out articles published at or before this time (includes buffer)

        Returns:
            List of NewsItem objects (one per watchlist symbol), or empty list if invalid/filtered
        """
        # Validate required fields
        headline = article.get('headline', '').strip()
        url = article.get('url', '').strip()
        datetime_epoch = article.get('datetime', 0)

        if not headline or not url or datetime_epoch <= 0:
            return []

        # Convert epoch timestamp to UTC datetime
        try:
            published = datetime.fromtimestamp(datetime_epoch, tz=timezone.utc)
        except (ValueError, OSError) as e:
            logger.debug(f"Skipping macro news article due to invalid epoch {datetime_epoch}: {e}")
            return []

        # Filter by buffer_time (exclusive to avoid duplicates)
        if buffer_time and published <= buffer_time:
            return []

        # Extract watchlist symbols from 'related' field (returns list or ['ALL'])
        related = article.get('related', '').strip()
        symbols = self._extract_symbols_from_related(related)

        # Extract other fields with defaults
        source = article.get('source', '').strip() or 'Finnhub'
        summary = article.get('summary', '').strip()
        content = summary if summary else None

        # Create one NewsItem per symbol
        news_items = []
        for symbol in symbols:
            try:
                news_item = NewsItem(
                    symbol=symbol,
                    url=url,
                    headline=headline,
                    published=published,
                    source=source,
                    content=content
                )
                news_items.append(news_item)
            except ValueError as e:
                # NewsItem validation failed for this symbol, skip it
                logger.debug(f"NewsItem validation failed for {symbol} (url={url}): {e}")
                continue

        return news_items

    def _extract_symbols_from_related(self, related: str | None) -> list[str]:
        """
        Extract watchlist symbols from Finnhub 'related' field.

        Filters related symbols to only those on our watchlist.
        Fallback behavior:
          - If related is empty/blank → ['ALL'] (macro-wide headline)
          - If related has symbols but none on our watchlist → [] (drop; no ALL)

        Args:
            related: Comma-separated symbols or empty string from API response

        Returns:
            List of watchlist symbols or ['ALL'] fallback

        Examples:
            Watchlist: [AAPL, TSLA]
            "" → ['ALL']
            "AAPL,MSFT" → ['AAPL'] (MSFT not on watchlist)
            "GOOGL" → ['ALL'] (not on watchlist)
            "AAPL,TSLA" → ['AAPL', 'TSLA']
            "  aapl  , tsla  " → ['AAPL', 'TSLA']
        """
        # Empty or blank related field → ALL
        if not related or not related.strip():
            return ['ALL']

        # Parse, dedupe, and filter to watchlist (order-preserving)
        return parse_symbols(related, filter_to=self.symbols, validate=True, log_label='RELATED')
