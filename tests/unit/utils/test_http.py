"""
Tests for utils.http module (get_json_with_retry).
Use monkeypatch to stub httpx.get; count calls; simulate status codes and JSON.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
import json

import httpx
from data.base import DataSourceError
from utils.http import get_json_with_retry
from utils.retry import RetryableError



class TestGetJsonWithRetry:
    """Test get_json_with_retry function"""
    
    @pytest.mark.asyncio
    async def test_200_ok_valid_json(self, mock_http_client):
        """Test 200 OK with valid JSON returns parsed object"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value", "number": 42}
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        result = await get_json_with_retry(
            "https://example.com/api",
            timeout=10,
            max_retries=3
        )
        
        assert result == {"key": "value", "number": 42}
        assert call_count == 1  # No retries for success
    
    @pytest.mark.asyncio
    async def test_200_ok_invalid_json(self, mock_http_client):
        """Test 200 OK with invalid JSON raises DataSourceError without retry"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with pytest.raises(DataSourceError) as exc_info:
            await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3
            )
        
        assert "Invalid JSON response" in str(exc_info.value)
        assert call_count == 1  # No retries for data errors
    
    @pytest.mark.asyncio
    async def test_204_no_content(self, mock_http_client):
        """Test 204 No Content returns None"""
        mock_response = Mock()
        mock_response.status_code = 204
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        result = await get_json_with_retry(
            "https://example.com/api",
            timeout=10,
            max_retries=3
        )
        
        assert result is None
        assert call_count == 1  # No retries for success
    
    @pytest.mark.asyncio
    async def test_401_403_auth_errors(self, mock_http_client):
        """Test 401/403 auth errors raise DataSourceError without retry"""
        for status_code in [401, 403]:
            mock_response = Mock()
            mock_response.status_code = status_code
            
            call_count = 0
            async def mock_get(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return mock_response
            
            # Use the fixture - much cleaner!
            mock_http_client(mock_get)
            
            with pytest.raises(DataSourceError) as exc_info:
                await get_json_with_retry(
                    "https://example.com/api",
                    timeout=10,
                    max_retries=3
                )
            
            assert "Authentication failed" in str(exc_info.value)
            assert call_count == 1  # No retries for auth errors
    
    @pytest.mark.asyncio
    async def test_other_4xx_errors(self, mock_http_client):
        """Test other 4xx errors (e.g., 404) raise DataSourceError without retry"""
        mock_response = Mock()
        mock_response.status_code = 404
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with pytest.raises(DataSourceError) as exc_info:
            await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3
            )
        
        assert "Client error (status 404)" in str(exc_info.value)
        assert call_count == 1  # No retries for client errors
    
    @pytest.mark.asyncio
    async def test_429_numeric_retry_after(self, mock_http_client):
        """Test 429 with numeric Retry-After header"""
        responses = [
            Mock(status_code=429, headers={"Retry-After": "0.01"}),  # Small delay for testing
            Mock(status_code=429, headers={"Retry-After": "0.01"}),
            Mock(status_code=200, json=Mock(return_value={"success": True}))
        ]
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            response = responses[call_count]
            call_count += 1
            return response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            result = await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3
            )
            
            assert result == {"success": True}
            assert call_count == 3  # Initial + 2 retries
            
            # Verify Retry-After delays were used
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 2
            assert sleep_calls[0][0][0] == pytest.approx(0.01)
            assert sleep_calls[1][0][0] == pytest.approx(0.01)
    
    @pytest.mark.asyncio
    async def test_429_http_date_retry_after(self, mock_http_client):
        """Test 429 with HTTP-date Retry-After header"""
        # Use 1.0 second future to distinguish from exponential backoff minimum (0.1s)
        future_time = datetime.now(timezone.utc) + timedelta(seconds=1.0)
        http_date = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        responses = [
            Mock(status_code=429, headers={"Retry-After": http_date}),
            Mock(status_code=200, json=Mock(return_value={"success": True}))
        ]
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            response = responses[call_count]
            call_count += 1
            return response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            result = await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3
            )
            
            assert result == {"success": True}
            assert call_count == 2  # Initial + 1 retry
            
            # Verify HTTP-date was parsed and used
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 1
            delay = sleep_calls[0][0][0]
            
            # Parse the header ourselves to get expected value
            from utils.retry import parse_retry_after
            expected = parse_retry_after(http_date)
            assert expected is not None
            # Tight assertion: should be close to 1.0, definitely not 0.1 (exponential minimum)
            assert pytest.approx(expected, abs=0.2) == delay
    
    @pytest.mark.asyncio
    async def test_5xx_server_errors(self, mock_http_client):
        """Test 5xx server errors trigger retries"""
        responses = [
            Mock(status_code=503, headers={}),
            Mock(status_code=500, headers={}),
            Mock(status_code=200, json=Mock(return_value={"success": True}))
        ]
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            response = responses[call_count]
            call_count += 1
            return response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            result = await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3,
                base=0.25,
                mult=2.0,
                jitter=0.0  # Disable jitter for predictable testing
            )
            
            assert result == {"success": True}
            assert call_count == 3  # Initial + 2 retries
            
            # Should use exponential backoff since no Retry-After
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 2
            # Verify exponential backoff pattern
            first_delay = sleep_calls[0][0][0]
            second_delay = sleep_calls[1][0][0]
            assert first_delay < second_delay  # Increasing delays
    
    @pytest.mark.asyncio
    async def test_5xx_max_retries_exhausted(self, mock_http_client):
        """Test that last RetryableError is raised after max attempts"""
        mock_response = Mock(status_code=503, headers={})
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            with pytest.raises(RetryableError) as exc_info:
                await get_json_with_retry(
                    "https://example.com/api",
                    timeout=10,
                    max_retries=2  # Will try 3 times total
                )
            
            assert "Transient error (status 503)" in str(exc_info.value)
            assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_timeout_exception(self, mock_http_client):
        """Test httpx.TimeoutException triggers retry"""
        exceptions = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            None  # Success response on third attempt
        ]
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            exc = exceptions[call_count]
            call_count += 1
            if exc:
                raise exc
            return Mock(status_code=200, json=Mock(return_value={"success": True}))
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            result = await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3
            )
            
            assert result == {"success": True}
            assert call_count == 3  # Initial + 2 retries
            assert mock_sleep.call_count == 2  # Two sleep calls between attempts
    
    @pytest.mark.asyncio
    async def test_transport_error(self, mock_http_client):
        """Test httpx.TransportError triggers retry"""
        exceptions = [
            httpx.TransportError("connection failed"),
            None  # Success on second attempt
        ]
        
        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            exc = exceptions[call_count]
            call_count += 1
            if exc:
                raise exc
            return Mock(status_code=200, json=Mock(return_value={"success": True}))
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            result = await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=3
            )
            
            assert result == {"success": True}
            assert call_count == 2  # Initial + 1 retry
            assert mock_sleep.call_count == 1
    
    @pytest.mark.asyncio
    async def test_query_params_passed_through(self, mock_http_client):
        """Test that query params are passed through unchanged"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        
        captured_params = None
        async def mock_get(url, params=None, **kwargs):
            nonlocal captured_params
            captured_params = params
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        test_params = {"key": "value", "number": 42, "list": ["a", "b"]}
        result = await get_json_with_retry(
            "https://example.com/api",
            params=test_params,
            timeout=10,
            max_retries=3
        )
        
        assert result == {"result": "ok"}
        assert captured_params == test_params  # Params passed unchanged
    
    @pytest.mark.asyncio
    async def test_timeout_arg_is_forwarded(self, mock_http_client):
        """Test that timeout parameter is forwarded to httpx.get"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        
        captured = {}
        async def mock_get(url, params=None, timeout=None, **kwargs):
            captured["timeout"] = timeout
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        await get_json_with_retry(
            "https://example.com/api",
            timeout=7.5,
            max_retries=0
        )
        
        assert captured["timeout"] == 7.5  # Verify our timeout was used
    
    @pytest.mark.asyncio
    async def test_unexpected_status_raises(self, mock_http_client):
        """Test that unexpected status codes raise DataSourceError"""
        mock_response = Mock()
        mock_response.status_code = 302  # Redirect - not explicitly handled
        mock_response.headers = {}
        
        # Simple mock function that returns our response
        async def mock_get(*args, **kwargs):
            return mock_response
        
        # Use the fixture - much cleaner!
        mock_http_client(mock_get)
        
        with pytest.raises(DataSourceError) as exc_info:
            await get_json_with_retry(
                "https://example.com/api",
                timeout=10,
                max_retries=0
            )
        
        assert "Unexpected HTTP status: 302" in str(exc_info.value)