"""
Market hours utilities for US equity markets.

Handles session classification (pre-market, regular, after-hours) based on
Eastern Time trading hours, with automatic DST handling.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data.models import Session


def classify_us_session(ts_utc: datetime) -> Session:
    """
    Classify US equity market session from a UTC-aware timestamp.
    
    Trading sessions (Eastern Time):
    - Pre-market: 04:00 - 09:30 ET
    - Regular: 09:30 - 16:00 ET
    - After-hours: 16:00 - 20:00 ET
    - Closed: 20:00 - 04:00 ET
    
    Args:
        ts_utc: UTC-aware datetime timestamp
        
    Returns:
        Session enum (PRE, REG, or POST)
        
    Note:
        This is time-of-day logic only. Does not account for weekends,
        holidays, or other market closures. A timestamp on Christmas Day
        at 10:00 AM ET will still return Session.REG.
    """
    # Ensure timestamp is UTC-aware
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=timezone.utc)
    else:
        ts_utc = ts_utc.astimezone(timezone.utc)
    
    # Convert to Eastern Time (handles DST automatically)
    et = ts_utc.astimezone(ZoneInfo("America/New_York"))
    
    # Calculate minutes since midnight for easier comparison
    minutes = et.hour * 60 + et.minute
    
    # Define session boundaries in minutes since midnight ET
    PRE_START = 4 * 60           # 04:00 ET = 240 minutes
    REG_START = 9 * 60 + 30      # 09:30 ET = 570 minutes
    POST_START = 16 * 60         # 16:00 ET = 960 minutes
    POST_END = 20 * 60           # 20:00 ET = 1200 minutes
    
    # Classify based on ET time
    if PRE_START <= minutes < REG_START:
        return Session.PRE
    elif REG_START <= minutes < POST_START:
        return Session.REG
    elif POST_START <= minutes < POST_END:
        return Session.POST
    else:
        # Outside extended hours (overnight/early morning)
        return Session.CLOSED
