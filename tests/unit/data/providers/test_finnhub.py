"""
Tests for Finnhub provider implementations.
Tests FinnhubClient, FinnhubNewsProvider, and FinnhubPriceProvider.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from config.providers.finnhub import FinnhubSettings
from config.retry import DEFAULT_DATA_RETRY
from data.providers.finnhub import FinnhubClient, FinnhubNewsProvider, FinnhubPriceProvider
from data.models import NewsItem, PriceData, Session


class TestFinnhubClient:
    """Test FinnhubClient HTTP wrapper"""
    
    @pytest.mark.asyncio
    async def test_builds_url_correctly(self, monkeypatch):
        """Test that client builds correct URL from base_url + path"""
        settings = FinnhubSettings(api_key='test_key')
        client = FinnhubClient(settings)
        
        captured_args = {}
        async def mock_get_json(*args, **kwargs):
            captured_args['url'] = args[0]
            captured_args['params'] = kwargs.get('params', {})
            return {'status': 'ok'}
        
        monkeypatch.setattr('data.providers.finnhub.get_json_with_retry', mock_get_json)
        
        await client.get('/quote')
        
        assert captured_args['url'] == 'https://finnhub.io/api/v1/quote'
    
    @pytest.mark.asyncio
    async def test_injects_token_into_params(self, monkeypatch):
        """Test that API token is added to params"""
        settings = FinnhubSettings(api_key='secret_token_123')
        client = FinnhubClient(settings)
        
        captured_args = {}
        async def mock_get_json(*args, **kwargs):
            captured_args['params'] = kwargs.get('params', {})
            return {'status': 'ok'}
        
        monkeypatch.setattr('data.providers.finnhub.get_json_with_retry', mock_get_json)
        
        await client.get('/company-news', params={'symbol': 'AAPL', 'from': '2024-01-01'})
        
        assert captured_args['params'] == {
            'symbol': 'AAPL',
            'from': '2024-01-01',
            'token': 'secret_token_123'
        }
    
    @pytest.mark.asyncio
    async def test_forwards_timeout_settings(self, monkeypatch):
        """Test that retry config settings are forwarded correctly"""
        settings = FinnhubSettings(api_key='test_key')
        client = FinnhubClient(settings)
        
        captured_args = {}
        async def mock_get_json(*args, **kwargs):
            captured_args.update(kwargs)
            return {'status': 'ok'}
        
        monkeypatch.setattr('data.providers.finnhub.get_json_with_retry', mock_get_json)
        
        await client.get('/quote')
        
        assert captured_args['timeout'] == DEFAULT_DATA_RETRY.timeout_seconds
        assert captured_args['max_retries'] == DEFAULT_DATA_RETRY.max_retries
        assert captured_args['base'] == DEFAULT_DATA_RETRY.base
        assert captured_args['mult'] == DEFAULT_DATA_RETRY.mult
        assert captured_args['jitter'] == DEFAULT_DATA_RETRY.jitter


class TestFinnhubNewsProvider:
    """Test FinnhubNewsProvider news fetching and parsing"""
    
    @pytest.mark.asyncio
    async def test_date_window_with_since(self, monkeypatch):
        """Test date window calculation when since is provided"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        # Mock datetime to have consistent "now"
        from datetime import timedelta as real_timedelta
        class MockDatetime:
            @staticmethod
            def now(tz):
                return datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
            
            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)
        
        # Also need to provide timedelta and timezone from the mock
        MockDatetime.timedelta = real_timedelta
        MockDatetime.timezone = timezone
        
        import data.providers.finnhub
        monkeypatch.setattr(data.providers.finnhub, 'datetime', MockDatetime)
        monkeypatch.setattr(data.providers.finnhub, 'timedelta', real_timedelta)
        
        captured_params = {}
        async def mock_get(path, params=None):
            if path == '/company-news':
                if params:
                    captured_params.update(params)
                return []
            return None
        
        provider.client.get = mock_get
        
        since = datetime(2024, 1, 13, 5, 0, tzinfo=timezone.utc)
        await provider.fetch_incremental(since)
        
        # Should use min(since.date, yesterday) = 2024-01-13
        assert captured_params['from'] == '2024-01-13'
        assert captured_params['to'] == '2024-01-15'
    
    @pytest.mark.asyncio
    async def test_date_window_without_since(self, monkeypatch):
        """Test date window calculation when since is None"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        from datetime import timedelta as real_timedelta
        class MockDatetime:
            @staticmethod
            def now(tz):
                return datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
            
            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)
        
        MockDatetime.timedelta = real_timedelta
        MockDatetime.timezone = timezone
        
        import data.providers.finnhub
        monkeypatch.setattr(data.providers.finnhub, 'datetime', MockDatetime)
        monkeypatch.setattr(data.providers.finnhub, 'timedelta', real_timedelta)
        
        captured_params = {}
        async def mock_get(path, params=None):
            if path == '/company-news':
                if params:
                    captured_params.update(params)
                return []
            return None
        
        provider.client.get = mock_get
        
        await provider.fetch_incremental(None)
        
        # Should use 2 days ago
        assert captured_params['from'] == '2024-01-13'
        assert captured_params['to'] == '2024-01-15'
    
    @pytest.mark.asyncio
    async def test_filters_old_articles(self, monkeypatch):
        """Test that articles are filtered with 2-minute buffer (published <= buffer_time)"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        # Buffer: 1000 - 120 = 880 seconds
        news_fixture = [
            {'headline': 'Very Old', 'url': 'http://veryold.com', 'datetime': 500, 'source': 'Reuters'},     # Before buffer
            {'headline': 'Old News', 'url': 'http://old.com', 'datetime': 880, 'source': 'Reuters'},         # Exactly at buffer (filtered)
            {'headline': 'Buffer Zone', 'url': 'http://buffer.com', 'datetime': 950, 'source': 'Bloomberg'}, # In buffer zone (kept)
            {'headline': 'At Watermark', 'url': 'http://exact.com', 'datetime': 1000, 'source': 'CNN'},      # At watermark (kept)
            {'headline': 'Latest News', 'url': 'http://latest.com', 'datetime': 1100, 'source': 'Yahoo'},    # After watermark (kept)
        ]
        
        async def mock_get(path, params=None):
            if path == '/company-news':
                return news_fixture
            return None
        
        provider.client.get = mock_get
        
        # Set since to datetime(1000)
        since = datetime.fromtimestamp(1000, tz=timezone.utc)
        results = await provider.fetch_incremental(since)
        
        # Should keep articles at 950, 1000, and 1100 (3 articles)
        assert len(results) == 3
        assert results[0].headline == 'Buffer Zone'    # In the 2-minute buffer window
        assert results[1].headline == 'At Watermark'   # Exactly at watermark (now kept!)
        assert results[2].headline == 'Latest News'    # After watermark
    
    @pytest.mark.asyncio
    async def test_parses_valid_article(self, monkeypatch):
        """Test parsing of valid article with all fields"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['TSLA'])
        
        news_fixture = [{
            'headline': 'Tesla Stock Rises',
            'url': 'https://example.com/tesla-news',
            'datetime': 1705320000,  # 2024-01-15 12:00:00 UTC
            'source': 'Reuters',
            'summary': 'Tesla stock rose 5% today on strong earnings.'
        }]
        
        async def mock_get(path, params=None):
            if path == '/company-news':
                return news_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        item = results[0]
        assert item.symbol == 'TSLA'
        assert item.headline == 'Tesla Stock Rises'
        assert item.url == 'https://example.com/tesla-news'
        assert item.source == 'Reuters'
        assert item.content == 'Tesla stock rose 5% today on strong earnings.'  # summary → content
        assert item.published == datetime.fromtimestamp(1705320000, tz=timezone.utc)
    
    @pytest.mark.asyncio
    async def test_skips_missing_headline(self, monkeypatch):
        """Test that articles without headline are skipped"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        news_fixture = [
            {'url': 'http://no-headline.com', 'datetime': 1705320000},
            {'headline': '', 'url': 'http://empty-headline.com', 'datetime': 1705320000},
            {'headline': 'Valid News', 'url': 'http://valid.com', 'datetime': 1705320000}
        ]
        
        async def mock_get(path, params=None):
            if path == '/company-news':
                return news_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        assert results[0].headline == 'Valid News'
    
    @pytest.mark.asyncio
    async def test_skips_invalid_epoch(self, monkeypatch):
        """Test that articles with invalid epoch timestamps are skipped"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        news_fixture = [
            {'headline': 'Zero Epoch', 'url': 'http://zero.com', 'datetime': 0},
            {'headline': 'Negative Epoch', 'url': 'http://negative.com', 'datetime': -100},
            {'headline': 'Valid News', 'url': 'http://valid.com', 'datetime': 1705320000}
        ]
        
        async def mock_get(path, params=None):
            if path == '/company-news':
                return news_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        assert results[0].headline == 'Valid News'
    
    @pytest.mark.asyncio
    async def test_per_symbol_isolation(self, monkeypatch):
        """Test that error in one symbol doesn't affect others"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['FAIL', 'AAPL', 'TSLA'])
        
        call_count = 0
        async def mock_get(path, params=None):
            nonlocal call_count
            call_count += 1
            
            if path == '/company-news' and params:
                symbol = params.get('symbol')
                if symbol == 'FAIL':
                    raise Exception('API error for FAIL symbol')
                elif symbol == 'AAPL':
                    return [{'headline': 'Apple News', 'url': 'http://apple.com', 'datetime': 1705320000}]
                elif symbol == 'TSLA':
                    return [{'headline': 'Tesla News', 'url': 'http://tesla.com', 'datetime': 1705320000}]
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert call_count == 3  # All symbols attempted
        assert len(results) == 2  # Only successful ones returned
        headlines = [r.headline for r in results]
        assert 'Apple News' in headlines
        assert 'Tesla News' in headlines
    
    @pytest.mark.asyncio
    async def test_validate_connection_success(self, monkeypatch):
        """Test validate_connection returns True on success"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return {'c': 150.0, 't': 1705320000}
            return None
        
        provider.client.get = mock_get
        
        result = await provider.validate_connection()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, monkeypatch):
        """Test validate_connection returns False on exception"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubNewsProvider(settings, ['AAPL'])
        
        async def mock_get(path, params=None):
            raise Exception('Connection failed')
        
        provider.client.get = mock_get
        
        result = await provider.validate_connection()
        assert result is False


class TestFinnhubPriceProvider:
    """Test FinnhubPriceProvider quote fetching and parsing"""
    
    @pytest.mark.asyncio
    async def test_requires_positive_price(self, monkeypatch):
        """Test that quotes with c <= 0 are skipped"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        quote_fixture = {'c': 0, 't': 1705320000, 'h': 125, 'l': 122}
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return quote_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_decimal_conversion(self, monkeypatch):
        """Test that price is converted to Decimal with string precision"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        quote_fixture = {'c': 123.45, 't': 1705320000}
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return quote_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        assert results[0].price == Decimal('123.45')
        assert isinstance(results[0].price, Decimal)
    
    @pytest.mark.asyncio
    async def test_fallback_timestamp_missing_t(self, monkeypatch):
        """Test fallback to now() when 't' field is missing"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        # Mock datetime.now
        fixed_now = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now
            
            @staticmethod
            def fromtimestamp(ts, tz):
                return datetime.fromtimestamp(ts, tz)
        
        monkeypatch.setattr('data.providers.finnhub.datetime', MockDatetime)
        
        quote_fixture = {'c': 150.0}  # No 't' field
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return quote_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        assert results[0].timestamp == fixed_now
    
    @pytest.mark.asyncio
    async def test_fallback_timestamp_invalid_t(self, monkeypatch):
        """Test fallback to now() when 't' field is invalid"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        fixed_now = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        class MockDatetime:
            @staticmethod
            def now(tz):
                return fixed_now
            
            @staticmethod
            def fromtimestamp(ts, tz):
                if ts == -999999999999:  # Invalid timestamp
                    raise OSError('Invalid timestamp')
                return datetime.fromtimestamp(ts, tz)
        
        monkeypatch.setattr('data.providers.finnhub.datetime', MockDatetime)
        
        quote_fixture = {'c': 150.0, 't': -999999999999}
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return quote_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        assert results[0].timestamp == fixed_now
    
    @pytest.mark.asyncio
    async def test_defaults_session_and_volume(self, monkeypatch):
        """Test session classification and default volume"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        # 15:00:00 UTC = 10:00:00 ET (REG session)
        reg_dt_utc = datetime(2024, 1, 17, 15, 0, tzinfo=timezone.utc)
        quote_fixture = {'c': 150.0, 't': int(reg_dt_utc.timestamp())}
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return quote_fixture
            return None
        
        provider.client.get = mock_get
        
        results = await provider.fetch_incremental()
        
        assert len(results) == 1
        assert results[0].session == Session.REG
        assert results[0].volume is None
    
    @pytest.mark.asyncio
    async def test_validate_connection_success(self, monkeypatch):
        """Test validate_connection returns True on success"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        async def mock_get(path, params=None):
            if path == '/quote':
                return {'c': 150.0, 't': 1705320000}
            return None
        
        provider.client.get = mock_get
        
        result = await provider.validate_connection()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, monkeypatch):
        """Test validate_connection returns False on exception"""
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        async def mock_get(path, params=None):
            raise Exception('Connection failed')
        
        provider.client.get = mock_get
        
        result = await provider.validate_connection()
        assert result is False
