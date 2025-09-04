"""
Tests for utils.retry module.
Focus on behaviors we rely on in v0.2.1.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from utils.retry import parse_retry_after, retry_and_call, RetryableError


class TestParseRetryAfter:
    """Test parse_retry_after function"""

    def test_numeric_seconds(self):
        """Test parsing numeric seconds"""
        assert parse_retry_after("120") == 120.0
        assert parse_retry_after("0") == 0.0
        assert parse_retry_after("5.5") == 5.5
        
    def test_numeric_negative_floored(self):
        """Test negative values are floored to 0"""
        assert parse_retry_after("-10") == 0.0
        
    def test_http_date_future(self):
        """Test HTTP-date parsing for future dates"""
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        http_date = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        result = parse_retry_after(http_date)
        assert result is not None
        assert result >= 4.0  # Allow some time for execution
        assert result <= 6.0  # But not too much
        
    def test_http_date_past(self):
        """Test HTTP-date parsing for past dates (floored to 0)"""
        past_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        http_date = past_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        result = parse_retry_after(http_date)
        assert result == 0.0
        
    def test_invalid_header(self):
        """Test invalid header returns None"""
        assert parse_retry_after("garbage") is None
        assert parse_retry_after("") is None
        assert parse_retry_after(None) is None
        assert parse_retry_after("not-a-number-or-date") is None


class TestRetryAndCall:
    """Test retry_and_call function"""
    
    @pytest.mark.asyncio
    async def test_retry_after_honored(self):
        """Test that Retry-After is honored over exponential backoff"""
        op = AsyncMock(side_effect=[
            RetryableError("error 1", retry_after=0.01),  # Small delay for testing
            RetryableError("error 2", retry_after=0.01),
            "success"
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await retry_and_call(op, attempts=3)
            
            assert result == "success"
            assert op.call_count == 3
            
            # Verify delays used Retry-After value (0.01)
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 2
            assert sleep_calls[0][0][0] == pytest.approx(0.01)
            assert sleep_calls[1][0][0] == pytest.approx(0.01)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff when no retry_after"""
        op = AsyncMock(side_effect=[
            RetryableError("error 1"),
            RetryableError("error 2"),
            RetryableError("error 3"),
            "success"
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await retry_and_call(
                op, 
                attempts=4, 
                base=0.25, 
                mult=2.0,
                jitter=0.0  # Disable jitter for predictable testing
            )
            
            assert result == "success"
            assert op.call_count == 4
            
            # Verify delays are increasing (exponential backoff)
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 3
            
            # First delay: base * (mult^0) = 0.25
            # Second delay: base * (mult^1) = 0.5
            # Third delay: base * (mult^2) = 1.0
            # (with minimum of 0.1 enforced)
            first_delay = sleep_calls[0][0][0]
            second_delay = sleep_calls[1][0][0]
            third_delay = sleep_calls[2][0][0]
            
            assert first_delay < second_delay < third_delay
            assert first_delay >= 0.1  # Minimum delay
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_with_jitter(self):
        """Test that jitter is applied to exponential backoff"""
        op = AsyncMock(side_effect=[
            RetryableError("error 1"),
            RetryableError("error 2"),
            "success"
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await retry_and_call(
                op,
                attempts=3,
                base=0.5,
                mult=2.0,
                jitter=0.1
            )
            
            assert result == "success"
            assert op.call_count == 3
            
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) == 2
            
            # Verify delays are non-zero and have some variation
            delays = [call[0][0] for call in sleep_calls]
            assert all(d > 0 for d in delays)
            
            # With jitter, exact values will vary but should be within expected range
            # First delay: 0.5 ± 0.1
            assert 0.4 <= delays[0] <= 0.6
            # Second delay: 1.0 ± 0.1  
            assert 0.9 <= delays[1] <= 1.1
    
    @pytest.mark.asyncio
    async def test_gives_up_and_surfaces_last_error(self):
        """Test that last exception is propagated after max attempts"""
        op = AsyncMock(side_effect=[
            RetryableError("error 1"),
            RetryableError("error 2"),
            RetryableError("final error")
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(RetryableError) as exc_info:
                await retry_and_call(op, attempts=3)
            
            assert str(exc_info.value) == "final error"
            assert op.call_count == 3
    
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test immediate success without retries"""
        op = AsyncMock(return_value="immediate success")
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await retry_and_call(op)
            
            assert result == "immediate success"
            assert op.call_count == 1
            assert mock_sleep.call_count == 0
    
    @pytest.mark.asyncio
    async def test_non_retryable_error_propagates(self):
        """Test that non-RetryableError exceptions are not retried"""
        op = AsyncMock(side_effect=ValueError("not retryable"))
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError) as exc_info:
                await retry_and_call(op)
            
            assert str(exc_info.value) == "not retryable"
            assert op.call_count == 1
            assert mock_sleep.call_count == 0  # No retry attempts
    
    @pytest.mark.asyncio
    async def test_retryable_then_non_retryable_error(self):
        """Test retryable error followed by non-retryable error stops immediately"""
        op = AsyncMock(side_effect=[
            RetryableError("network timeout"),  # First attempt: retryable
            ValueError("invalid API key")       # Second attempt: non-retryable  
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError) as exc_info:
                await retry_and_call(op, attempts=3)
            
            assert str(exc_info.value) == "invalid API key"
            assert op.call_count == 2  # Only 2 calls: retry once, then stop
            assert mock_sleep.call_count == 1  # Only 1 sleep between attempts