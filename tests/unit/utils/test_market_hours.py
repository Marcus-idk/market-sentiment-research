"""
Market hours classification tests.
Tests US equity market session detection based on Eastern Time.
"""

import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data.models import Session
from utils.market_hours import classify_us_session


class TestClassifyUsSession:
    """Test US market session classification"""
    
    def test_regular_session_hours(self):
        """Test regular trading session (9:30 AM - 4:00 PM ET)"""
        # Test various times during regular session
        test_cases = [
            # datetime UTC, expected session
            # 9:30 AM ET = 13:30 UTC (EDT) or 14:30 UTC (EST)
            (datetime(2024, 7, 15, 13, 30, tzinfo=timezone.utc), Session.REG),  # 9:30 AM EDT
            (datetime(2024, 7, 15, 14, 0, tzinfo=timezone.utc), Session.REG),   # 10:00 AM EDT
            (datetime(2024, 7, 15, 18, 0, tzinfo=timezone.utc), Session.REG),   # 2:00 PM EDT
            (datetime(2024, 7, 15, 19, 59, tzinfo=timezone.utc), Session.REG),  # 3:59 PM EDT
            # Winter (EST)
            (datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc), Session.REG),  # 9:30 AM EST
            (datetime(2024, 1, 15, 20, 59, tzinfo=timezone.utc), Session.REG),  # 3:59 PM EST
        ]
        
        for ts_utc, expected in test_cases:
            result = classify_us_session(ts_utc)
            assert result == expected, f"Failed for {ts_utc}: expected {expected}, got {result}"
    
    def test_premarket_session_hours(self):
        """Test pre-market session (4:00 AM - 9:30 AM ET)"""
        test_cases = [
            # Summer (EDT = UTC-4)
            (datetime(2024, 7, 15, 8, 0, tzinfo=timezone.utc), Session.PRE),    # 4:00 AM EDT
            (datetime(2024, 7, 15, 8, 1, tzinfo=timezone.utc), Session.PRE),    # 4:01 AM EDT
            (datetime(2024, 7, 15, 10, 0, tzinfo=timezone.utc), Session.PRE),   # 6:00 AM EDT
            (datetime(2024, 7, 15, 13, 29, tzinfo=timezone.utc), Session.PRE),  # 9:29 AM EDT
            # Winter (EST = UTC-5)
            (datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc), Session.PRE),    # 4:00 AM EST
            (datetime(2024, 1, 15, 14, 29, tzinfo=timezone.utc), Session.PRE),  # 9:29 AM EST
        ]
        
        for ts_utc, expected in test_cases:
            result = classify_us_session(ts_utc)
            assert result == expected, f"Failed for {ts_utc}: expected {expected}, got {result}"
    
    def test_afterhours_session_hours(self):
        """Test after-hours session (4:00 PM - 8:00 PM ET)"""
        test_cases = [
            # Summer (EDT)
            (datetime(2024, 7, 15, 20, 0, tzinfo=timezone.utc), Session.POST),   # 4:00 PM EDT
            (datetime(2024, 7, 15, 20, 1, tzinfo=timezone.utc), Session.POST),   # 4:01 PM EDT
            (datetime(2024, 7, 15, 22, 0, tzinfo=timezone.utc), Session.POST),   # 6:00 PM EDT
            (datetime(2024, 7, 15, 23, 59, tzinfo=timezone.utc), Session.POST),  # 7:59 PM EDT
            # Winter (EST)
            (datetime(2024, 1, 15, 21, 0, tzinfo=timezone.utc), Session.POST),   # 4:00 PM EST
            (datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc), Session.POST),   # 6:00 PM EST
            (datetime(2024, 2, 15, 0, 59, tzinfo=timezone.utc), Session.POST),   # 7:59 PM EST
        ]
        
        for ts_utc, expected in test_cases:
            result = classify_us_session(ts_utc)
            assert result == expected, f"Failed for {ts_utc}: expected {expected}, got {result}"
    
    def test_closed_session_hours(self):
        """Test closed/overnight session (8:00 PM - 4:00 AM ET)"""
        test_cases = [
            # Summer (EDT)
            (datetime(2024, 7, 15, 0, 0, tzinfo=timezone.utc), Session.CLOSED),   # 8:00 PM EDT (previous day)
            (datetime(2024, 7, 15, 2, 0, tzinfo=timezone.utc), Session.CLOSED),   # 10:00 PM EDT (previous day)
            (datetime(2024, 7, 15, 4, 0, tzinfo=timezone.utc), Session.CLOSED),   # 12:00 AM EDT
            (datetime(2024, 7, 15, 7, 59, tzinfo=timezone.utc), Session.CLOSED),  # 3:59 AM EDT
            # Winter (EST)
            (datetime(2024, 1, 15, 1, 0, tzinfo=timezone.utc), Session.CLOSED),   # 8:00 PM EST (previous day)
            (datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc), Session.CLOSED),   # 10:00 PM EST (previous day)
            (datetime(2024, 1, 15, 8, 59, tzinfo=timezone.utc), Session.CLOSED),  # 3:59 AM EST
        ]
        
        for ts_utc, expected in test_cases:
            result = classify_us_session(ts_utc)
            assert result == expected, f"Failed for {ts_utc}: expected {expected}, got {result}"
    
    def test_session_boundaries_exact(self):
        """Test exact boundary times between sessions"""
        # Using a summer date (July 15, 2024) - EDT (UTC-4)
        test_cases = [
            # Exact boundaries in EDT
            (datetime(2024, 7, 15, 8, 0, 0, tzinfo=timezone.utc), Session.PRE),      # 4:00:00 AM EDT
            (datetime(2024, 7, 15, 7, 59, 59, tzinfo=timezone.utc), Session.CLOSED), # 3:59:59 AM EDT
            (datetime(2024, 7, 15, 13, 30, 0, tzinfo=timezone.utc), Session.REG),    # 9:30:00 AM EDT
            (datetime(2024, 7, 15, 13, 29, 59, tzinfo=timezone.utc), Session.PRE),   # 9:29:59 AM EDT
            (datetime(2024, 7, 15, 20, 0, 0, tzinfo=timezone.utc), Session.POST),    # 4:00:00 PM EDT
            (datetime(2024, 7, 15, 19, 59, 59, tzinfo=timezone.utc), Session.REG),   # 3:59:59 PM EDT
            (datetime(2024, 7, 16, 0, 0, 0, tzinfo=timezone.utc), Session.CLOSED),   # 8:00:00 PM EDT
            (datetime(2024, 7, 15, 23, 59, 59, tzinfo=timezone.utc), Session.POST),  # 7:59:59 PM EDT
        ]
        
        for ts_utc, expected in test_cases:
            result = classify_us_session(ts_utc)
            assert result == expected, f"Boundary test failed for {ts_utc}: expected {expected}, got {result}"
    
    def test_dst_transition_spring_forward(self):
        """Test session classification during spring DST transition (2nd Sunday of March)"""
        # 2024: DST starts March 10 at 2:00 AM (clocks spring forward to 3:00 AM)
        # March 8 (Friday before): EST (UTC-5)
        # March 11 (Monday after): EDT (UTC-4)
        
        # Friday March 8, 2024 - still EST
        friday_9_30am_est = datetime(2024, 3, 8, 14, 30, tzinfo=timezone.utc)  # 9:30 AM EST
        assert classify_us_session(friday_9_30am_est) == Session.REG
        
        # Monday March 11, 2024 - now EDT
        monday_9_30am_edt = datetime(2024, 3, 11, 13, 30, tzinfo=timezone.utc)  # 9:30 AM EDT
        assert classify_us_session(monday_9_30am_edt) == Session.REG
    
    def test_dst_transition_fall_back(self):
        """Test session classification during fall DST transition (1st Sunday of November)"""
        # 2024: DST ends November 3 at 2:00 AM (clocks fall back to 1:00 AM)
        # November 1 (Friday before): EDT (UTC-4)
        # November 4 (Monday after): EST (UTC-5)
        
        # Friday November 1, 2024 - still EDT
        friday_9_30am_edt = datetime(2024, 11, 1, 13, 30, tzinfo=timezone.utc)  # 9:30 AM EDT
        assert classify_us_session(friday_9_30am_edt) == Session.REG
        
        # Monday November 4, 2024 - now EST
        monday_9_30am_est = datetime(2024, 11, 4, 14, 30, tzinfo=timezone.utc)  # 9:30 AM EST
        assert classify_us_session(monday_9_30am_est) == Session.REG
    
    def test_naive_datetime_handling(self):
        """Test that naive datetimes are treated as UTC"""
        # Naive datetime (no timezone)
        naive_dt = datetime(2024, 7, 15, 14, 0)  # No tzinfo
        result = classify_us_session(naive_dt)
        
        # Should be treated as UTC and converted
        # 14:00 UTC = 10:00 AM EDT = Regular session
        assert result == Session.REG
    
    def test_different_timezone_inputs(self):
        """Test inputs with different timezones are correctly converted"""
        # Create ET timezone object
        et_tz = ZoneInfo("America/New_York")
        
        # 10:00 AM ET on July 15, 2024
        et_time = datetime(2024, 7, 15, 10, 0, tzinfo=et_tz)
        
        # Convert to UTC for comparison
        utc_time = et_time.astimezone(timezone.utc)
        
        # Both should give same result (REG session)
        assert classify_us_session(et_time) == Session.REG
        assert classify_us_session(utc_time) == Session.REG
    
    def test_weekend_dates(self):
        """Test that weekend dates still classify by time (not market calendar)
        
        Note: This function is intentionally not calendar-aware. It only checks
        time-of-day, so weekends and holidays still return session classifications.
        """
        # Saturday July 13, 2024 at 10:00 AM EDT (14:00 UTC)
        saturday = datetime(2024, 7, 13, 14, 0, tzinfo=timezone.utc)
        
        # Should still return REG based on time-of-day
        # (function doesn't check for weekends/holidays)
        assert classify_us_session(saturday) == Session.REG
        
        # Sunday at 2:00 AM EDT (6:00 UTC) - should be CLOSED
        sunday_night = datetime(2024, 7, 14, 6, 0, tzinfo=timezone.utc)
        assert classify_us_session(sunday_night) == Session.CLOSED
    
    def test_microsecond_precision(self):
        """Test classification with microsecond precision"""
        # Test right at the boundary with microseconds
        # 9:29:59.999999 AM EDT should be PRE
        pre_boundary = datetime(2024, 7, 15, 13, 29, 59, 999999, tzinfo=timezone.utc)
        assert classify_us_session(pre_boundary) == Session.PRE
        
        # 9:30:00.000001 AM EDT should be REG
        reg_boundary = datetime(2024, 7, 15, 13, 30, 0, 1, tzinfo=timezone.utc)
        assert classify_us_session(reg_boundary) == Session.REG
    
    def test_year_variations(self):
        """Test classification works across different years"""
        years = [2020, 2021, 2022, 2023, 2024, 2025]
        
        for year in years:
            # Test a regular trading hour in summer (10:00 AM EDT = 14:00 UTC)
            summer_reg = datetime(year, 7, 15, 14, 0, tzinfo=timezone.utc)
            assert classify_us_session(summer_reg) == Session.REG
            
            # Test a pre-market hour in winter (5:00 AM EST = 10:00 UTC)
            winter_pre = datetime(year, 1, 15, 10, 0, tzinfo=timezone.utc)
            assert classify_us_session(winter_pre) == Session.PRE