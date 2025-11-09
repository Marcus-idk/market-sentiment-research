"""US market session detection based on Eastern Time (ET)."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from data.models import Session
from utils import market_sessions
from utils.market_sessions import classify_us_session


class TestClassifyUsSession:
    """US market session classification"""

    @pytest.mark.parametrize(
        "ts_utc, expected",
        [
            # —— Regular (EDT, UTC-4) ——
            (datetime(2024, 7, 15, 13, 30, tzinfo=UTC), Session.REG),  # 09:30 ET
            (datetime(2024, 7, 15, 19, 59, tzinfo=UTC), Session.REG),  # 15:59 ET
            # —— Regular (EST, UTC-5) ——
            (datetime(2024, 1, 17, 14, 30, tzinfo=UTC), Session.REG),  # 09:30 ET
            (datetime(2024, 1, 17, 20, 59, tzinfo=UTC), Session.REG),  # 15:59 ET
            # —— Pre-market (EDT) ——
            (datetime(2024, 7, 15, 8, 0, tzinfo=UTC), Session.PRE),  # 04:00 ET
            (datetime(2024, 7, 15, 13, 29, tzinfo=UTC), Session.PRE),  # 09:29 ET
            # —— Pre-market (EST) ——
            (datetime(2024, 1, 17, 9, 0, tzinfo=UTC), Session.PRE),  # 04:00 ET
            (datetime(2024, 1, 17, 14, 29, tzinfo=UTC), Session.PRE),  # 09:29 ET
            # —— After-hours (EDT) ——
            (datetime(2024, 7, 15, 20, 0, tzinfo=UTC), Session.POST),  # 16:00 ET
            (datetime(2024, 7, 15, 23, 59, tzinfo=UTC), Session.POST),  # 19:59 ET
            # After-hours (EDT) end is exclusive at 20:00 ET:
            (datetime(2024, 7, 16, 0, 0, tzinfo=UTC), Session.CLOSED),  # 20:00 ET
            # —— After-hours (EST) ——
            (datetime(2024, 1, 17, 21, 0, tzinfo=UTC), Session.POST),  # 16:00 ET
            (datetime(2024, 2, 15, 0, 59, tzinfo=UTC), Session.POST),  # 19:59 ET
            # After-hours (EST) end is exclusive at 20:00 ET:
            (datetime(2024, 1, 18, 1, 0, tzinfo=UTC), Session.CLOSED),  # 20:00 ET
            # —— Closed (overnight pre-PRE) ——
            (datetime(2024, 7, 15, 7, 59, tzinfo=UTC), Session.CLOSED),  # 03:59 ET
            (datetime(2024, 1, 17, 8, 59, tzinfo=UTC), Session.CLOSED),  # 03:59 ET
        ],
    )
    def test_core_windows(self, ts_utc, expected):
        """Test core trading windows across EDT and EST timezones."""
        assert classify_us_session(ts_utc) == expected

    def test_exact_boundaries_and_precision(self):
        """Test precise session boundaries including microsecond precision."""
        # PRE start inclusive
        assert classify_us_session(datetime(2024, 7, 15, 8, 0, tzinfo=UTC)) == Session.PRE

        # PRE end exclusive / REG start inclusive
        assert (
            classify_us_session(datetime(2024, 7, 15, 13, 29, 59, 999999, tzinfo=UTC))
            == Session.PRE
        )
        assert classify_us_session(datetime(2024, 7, 15, 13, 30, 0, 1, tzinfo=UTC)) == Session.REG

        # POST start inclusive / POST end exclusive
        assert classify_us_session(datetime(2024, 7, 15, 20, 0, tzinfo=UTC)) == Session.POST
        assert classify_us_session(datetime(2024, 7, 16, 0, 0, tzinfo=UTC)) == Session.CLOSED

    def test_dst_transitions(self):
        """Test DST transitions maintain correct ET-based session classification."""
        # Spring forward: Mon 2024-03-11 09:30 ET = 13:30Z
        assert classify_us_session(datetime(2024, 3, 11, 13, 30, tzinfo=UTC)) == Session.REG
        # Fall back: Mon 2024-11-04 09:30 ET = 14:30Z
        assert classify_us_session(datetime(2024, 11, 4, 14, 30, tzinfo=UTC)) == Session.REG

    def test_weekends_holidays_early_closes(self):
        """Test weekends, major holidays, and early close days."""
        # Weekends → CLOSED
        assert (
            classify_us_session(datetime(2024, 7, 13, 14, 0, tzinfo=UTC)) == Session.CLOSED
        )  # Sat
        assert (
            classify_us_session(datetime(2024, 7, 14, 14, 0, tzinfo=UTC)) == Session.CLOSED
        )  # Sun

        # Major holidays → CLOSED
        for d in [
            (2024, 12, 25),
            (2024, 11, 28),
            (2024, 7, 4),
            (2024, 1, 1),
            (2024, 1, 15),
            (2024, 9, 2),
        ]:
            assert classify_us_session(datetime(*d, 14, 0, tzinfo=UTC)) == Session.CLOSED

        # Early close (Black Friday 2024-11-29): 13:00 ET close
        assert (
            classify_us_session(datetime(2024, 11, 29, 17, 30, tzinfo=UTC)) == Session.REG
        )  # 12:30 ET
        assert (
            classify_us_session(datetime(2024, 11, 29, 18, 30, tzinfo=UTC)) == Session.POST
        )  # 13:30 ET

        # Christmas Eve early close (2024-12-24)
        assert (
            classify_us_session(datetime(2024, 12, 24, 17, 30, tzinfo=UTC)) == Session.REG
        )  # 12:30 ET
        assert (
            classify_us_session(datetime(2024, 12, 24, 19, 0, tzinfo=UTC)) == Session.POST
        )  # 14:00 ET

    def test_input_tz_handling(self):
        """Test handling of different timezone inputs (naive, ET, UTC)."""
        # Naive is treated as UTC by implementation
        assert classify_us_session(datetime(2024, 7, 15, 14, 0)) == Session.REG  # 10:00 ET

        # ET-zoned input equals UTC after conversion
        et = ZoneInfo("America/New_York")
        et_dt = datetime(2024, 7, 15, 10, 0, tzinfo=et)  # 10:00 ET
        utc_dt = et_dt.astimezone(UTC)
        assert classify_us_session(et_dt) == Session.REG
        assert classify_us_session(utc_dt) == Session.REG

    def test_same_utc_time_diff_seasons(self):
        """Test same UTC time yields different sessions in EDT vs EST."""
        # 13:30 UTC → 09:30 ET in July (EDT) = REG
        assert classify_us_session(datetime(2024, 7, 15, 13, 30, tzinfo=UTC)) == Session.REG
        # 13:30 UTC → 08:30 ET in January (EST) = PRE
        assert classify_us_session(datetime(2024, 1, 17, 13, 30, tzinfo=UTC)) == Session.PRE

    def test_close_time_lookup_failure_falls_back_to_16_et_and_logs_warning(
        self, caplog, monkeypatch
    ):
        """Test graceful degradation when NYSE calendar close time lookup fails"""

        # Mock the calendar to raise an exception when accessing session_close
        def mock_session_close(session_label):
            raise KeyError("Mock calendar failure")

        # Replace instance method with direct assignment
        nyse_calendar = market_sessions._get_nyse_calendar()
        monkeypatch.setattr(nyse_calendar, "session_close", mock_session_close)

        # Test timestamp: 2024-01-17 21:00 UTC = 16:00 ET (Wednesday)
        # This is exactly at the regular close time
        ts = datetime(2024, 1, 17, 21, 0, tzinfo=UTC)

        with caplog.at_level(logging.WARNING):
            result = classify_us_session(ts)

        # Should fall back to 16:00 ET default (POST session starts at 16:00)
        assert result == Session.POST

        # Verify warning was logged about fallback
        assert any(
            "Could not determine session close time" in record.message
            and "falling back to 16:00 ET" in record.message
            for record in caplog.records
        )
