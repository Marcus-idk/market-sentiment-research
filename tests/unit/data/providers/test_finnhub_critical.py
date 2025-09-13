"""
Critical error handling tests for Finnhub providers.
Tests the most important error scenarios that could break production.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from config.providers.finnhub import FinnhubSettings
from data.providers.finnhub import FinnhubClient, FinnhubPriceProvider
from data.base import DataSourceError
from utils.retry import RetryableError


class TestFinnhubCriticalErrorHandling:
    """Test critical error scenarios that could break production"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_triggers_retry(self, mock_http_client):
        """Test that 429 rate limit errors trigger retry with backoff
        
        Finnhub free tier = 60 calls/minute. This WILL happen in production.
        """
        from unittest.mock import Mock, patch, AsyncMock
        
        settings = FinnhubSettings(api_key='test_key')
        client = FinnhubClient(settings)
        
        # Create response sequence: 429, 429, then 200 success
        responses = [
            Mock(status_code=429, headers={"Retry-After": "0.01"}),  # Small delay for testing
            Mock(status_code=429, headers={"Retry-After": "0.01"}),
            Mock(status_code=200, json=Mock(return_value={'c': 150.0, 't': 1705320000}))
        ]
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            response = responses[call_count]
            call_count += 1
            return response
        
        # Mock at HTTP client level (following established pattern)
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Should eventually succeed after retries
            result = await client.get('/quote', {'symbol': 'AAPL'})
            assert result == {'c': 150.0, 't': 1705320000}
            assert call_count == 3  # Initial + 2 retries = 3 total calls
            
            # Verify that sleep was called for retries
            assert mock_sleep.call_count == 2  # Two sleeps between 3 attempts
    
    @pytest.mark.asyncio
    async def test_auth_error_fails_fast(self, monkeypatch):
        """Test that 401 auth errors fail immediately without retry
        
        API keys expire or get revoked. Should fail fast, not waste time retrying.
        """
        settings = FinnhubSettings(api_key='invalid_key')
        client = FinnhubClient(settings)
        
        call_count = 0
        async def mock_get_json(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # 401 should not retry - DataSourceError is non-retryable
            raise DataSourceError("Authentication failed (status 401)")
        
        monkeypatch.setattr('data.providers.finnhub.get_json_with_retry', mock_get_json)
        
        # Should fail immediately
        with pytest.raises(DataSourceError) as exc_info:
            await client.get('/quote', {'symbol': 'AAPL'})
        
        assert "Authentication failed" in str(exc_info.value)
        assert call_count == 1  # No retries for auth errors
    
    @pytest.mark.asyncio
    async def test_rejects_invalid_prices(self):
        """Test rejection of negative/zero/invalid price data
        
        Bad price = bad trade = lost money. This is critical to test.
        """
        settings = FinnhubSettings(api_key='test_key')
        provider = FinnhubPriceProvider(settings, ['AAPL'])
        
        # Test negative price
        async def mock_get_negative(path, params=None):
            return {'c': -10.0, 't': 1705320000}  # Negative price
        
        provider.client.get = mock_get_negative
        results = await provider.fetch_incremental()
        assert len(results) == 0  # Should reject negative price
        
        # Test zero price
        async def mock_get_zero(path, params=None):
            return {'c': 0.0, 't': 1705320000}  # Zero price
        
        provider.client.get = mock_get_zero
        results = await provider.fetch_incremental()
        assert len(results) == 0  # Should reject zero price
        
        # Test invalid price (string)
        async def mock_get_string(path, params=None):
            return {'c': "invalid", 't': 1705320000}  # String price
        
        provider.client.get = mock_get_string
        results = await provider.fetch_incremental()
        assert len(results) == 0  # Should reject invalid price type
        
        # Test missing price field
        async def mock_get_missing(path, params=None):
            return {'t': 1705320000}  # No 'c' field
        
        provider.client.get = mock_get_missing
        results = await provider.fetch_incremental()
        assert len(results) == 0  # Should reject missing price
        
        # Test valid price to ensure we're not rejecting everything
        async def mock_get_valid(path, params=None):
            return {'c': 150.50, 't': 1705320000}  # Valid price
        
        provider.client.get = mock_get_valid
        results = await provider.fetch_incremental()
        assert len(results) == 1  # Should accept valid price
        assert results[0].price == Decimal('150.50')