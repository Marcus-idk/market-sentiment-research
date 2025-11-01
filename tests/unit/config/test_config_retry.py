"""Retry config tests: defaults, immutability, custom values."""

from dataclasses import FrozenInstanceError

import pytest

from config.retry import DEFAULT_DATA_RETRY, DEFAULT_LLM_RETRY, DataRetryConfig, LLMRetryConfig


class TestLLMRetryConfig:
    """Test LLMRetryConfig frozen dataclass"""

    def test_custom_values(self):
        """Test LLMRetryConfig can be instantiated with custom values"""
        config = LLMRetryConfig(timeout_seconds=500, max_retries=5, base=0.5, mult=3.0, jitter=0.2)

        assert config.timeout_seconds == 500
        assert config.max_retries == 5
        assert config.base == 0.5
        assert config.mult == 3.0
        assert config.jitter == 0.2

    def test_partial_custom_values(self):
        """Test LLMRetryConfig with some custom values and some defaults"""
        config = LLMRetryConfig(timeout_seconds=600, max_retries=10)

        assert config.timeout_seconds == 600
        assert config.max_retries == 10
        # These should still be defaults
        assert config.base == 0.25
        assert config.mult == 2.0
        assert config.jitter == 0.1

    def test_immutability(self):
        """Test LLMRetryConfig is frozen (immutable)"""
        config = LLMRetryConfig()

        with pytest.raises(FrozenInstanceError):
            config.timeout_seconds = 500

        with pytest.raises(FrozenInstanceError):
            config.max_retries = 10

        with pytest.raises(FrozenInstanceError):
            config.base = 0.5

    def test_default_instance(self):
        """Test DEFAULT_LLM_RETRY instance exists with correct values"""
        assert isinstance(DEFAULT_LLM_RETRY, LLMRetryConfig)
        assert DEFAULT_LLM_RETRY.timeout_seconds == 360
        assert DEFAULT_LLM_RETRY.max_retries == 3
        assert DEFAULT_LLM_RETRY.base == 0.25
        assert DEFAULT_LLM_RETRY.mult == 2.0
        assert DEFAULT_LLM_RETRY.jitter == 0.1

    def test_default_instance_immutable(self):
        """Test DEFAULT_LLM_RETRY instance cannot be modified"""
        with pytest.raises(FrozenInstanceError):
            DEFAULT_LLM_RETRY.timeout_seconds = 999


class TestDataRetryConfig:
    """Test DataRetryConfig frozen dataclass"""

    def test_custom_values(self):
        """Test DataRetryConfig can be instantiated with custom values"""
        config = DataRetryConfig(timeout_seconds=60, max_retries=4, base=0.3, mult=2.5, jitter=0.15)

        assert config.timeout_seconds == 60
        assert config.max_retries == 4
        assert config.base == 0.3
        assert config.mult == 2.5
        assert config.jitter == 0.15

    def test_partial_custom_values(self):
        """Test DataRetryConfig with some custom values and some defaults"""
        config = DataRetryConfig(timeout_seconds=45, max_retries=2)

        assert config.timeout_seconds == 45
        assert config.max_retries == 2
        # These should still be defaults
        assert config.base == 0.25
        assert config.mult == 2.0
        assert config.jitter == 0.1

    def test_immutability(self):
        """Test DataRetryConfig is frozen (immutable)"""
        config = DataRetryConfig()

        with pytest.raises(FrozenInstanceError):
            config.timeout_seconds = 100

        with pytest.raises(FrozenInstanceError):
            config.max_retries = 5

        with pytest.raises(FrozenInstanceError):
            config.jitter = 0.5

    def test_default_instance(self):
        """Test DEFAULT_DATA_RETRY instance exists with correct values"""
        assert isinstance(DEFAULT_DATA_RETRY, DataRetryConfig)
        assert DEFAULT_DATA_RETRY.timeout_seconds == 30
        assert DEFAULT_DATA_RETRY.max_retries == 3
        assert DEFAULT_DATA_RETRY.base == 0.25
        assert DEFAULT_DATA_RETRY.mult == 2.0
        assert DEFAULT_DATA_RETRY.jitter == 0.1

    def test_default_instance_immutable(self):
        """Test DEFAULT_DATA_RETRY instance cannot be modified"""
        with pytest.raises(FrozenInstanceError):
            DEFAULT_DATA_RETRY.timeout_seconds = 999


class TestRetryBusinessRules:
    """Test cross-config business rules for retry configurations"""

    def test_different_timeouts(self):
        """Test that LLM and Data configs have different default timeouts"""
        # This is an important business rule - LLMs need longer timeouts
        assert DEFAULT_LLM_RETRY.timeout_seconds > DEFAULT_DATA_RETRY.timeout_seconds
        assert DEFAULT_LLM_RETRY.timeout_seconds == 360
        assert DEFAULT_DATA_RETRY.timeout_seconds == 30
