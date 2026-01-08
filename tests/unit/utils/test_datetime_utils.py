"""Tests for utils/datetime_utils.py."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from utils.datetime_utils import (
    epoch_seconds_to_utc_datetime,
    normalize_to_utc,
)


class TestNormalizeToUtc:
    def test_naive_datetime_is_assumed_utc(self):
        """Naive datetimes are treated as UTC."""
        dt = normalize_to_utc(datetime(2024, 3, 10, 15, 45, 0))
        assert dt == datetime(2024, 3, 10, 15, 45, 0, tzinfo=UTC)

    def test_aware_datetime_is_converted_to_utc(self):
        """Aware datetimes are converted to UTC."""
        eastern = timezone(timedelta(hours=-5))
        dt = normalize_to_utc(datetime(2024, 3, 10, 10, 0, 0, tzinfo=eastern))
        assert dt == datetime(2024, 3, 10, 15, 0, 0, tzinfo=UTC)


class TestEpochSecondsToUtcDatetime:
    def test_epoch_zero_is_utc(self):
        """Epoch 0 maps to UTC 1970-01-01."""
        dt = epoch_seconds_to_utc_datetime(0)
        assert dt == datetime(1970, 1, 1, 0, 0, tzinfo=UTC)

    def test_epoch_float_is_utc(self):
        """Float epoch seconds convert to a UTC datetime."""
        dt = epoch_seconds_to_utc_datetime(1.0)
        assert dt == datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)

    def test_non_numeric_raises(self):
        """Non-numeric epoch inputs raise TypeError."""
        with pytest.raises(TypeError):
            epoch_seconds_to_utc_datetime("123")
