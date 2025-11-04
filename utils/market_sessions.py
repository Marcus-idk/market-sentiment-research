"""
Market sessions utilities for US equity markets.

Handles session classification (pre-market, regular, after-hours, closed)
based on Eastern Time trading hours and NYSE calendar, with automatic DST handling.
"""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import exchange_calendars as xcals
except ImportError as e:
    raise ImportError(
        "exchange_calendars is required for accurate market session classification. "
        "Market holidays and early closes cannot be detected without it. "
        "Install with: pip install 'exchange-calendars>=4.11,<5.0'"
    ) from e

from data.models import Session

logger = logging.getLogger(__name__)

# Cache NYSE calendar
_nyse_calendar = None


def _get_nyse_calendar():
    """Get or create cached NYSE calendar instance."""
    global _nyse_calendar
    if _nyse_calendar is None:
        _nyse_calendar = xcals.get_calendar("XNYS")
    return _nyse_calendar


def classify_us_session(ts_utc: datetime) -> Session:
    """
    Classify US equity market session from a UTC-aware timestamp.

    Trading sessions (Eastern Time):
    - Pre-market: 04:00 - 09:30 ET
    - Regular: 09:30 - 16:00 ET (or until 13:00 ET on early close days)
    - After-hours: 16:00 - 20:00 ET (or 13:00 - 20:00 ET on early close days)
    - Closed: Weekends, holidays, and outside trading hours

    Args:
        ts_utc: UTC-aware datetime timestamp

    Returns:
        Session enum (PRE, REG, POST, or CLOSED)

    Note:
        Uses NYSE calendar to detect holidays and early close days.
        Requires `exchange_calendars`; if not installed, an ImportError is raised at import time.
    """
    # Ensure timestamp is UTC-aware
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=UTC)
    else:
        ts_utc = ts_utc.astimezone(UTC)

    # Convert to Eastern Time (handles DST automatically)
    et = ts_utc.astimezone(ZoneInfo("America/New_York"))

    # Check if this is a trading day using NYSE calendar
    nyse = _get_nyse_calendar()

    # Convert date to pandas Timestamp label (calendar expects tz-naive)
    session_label = pd.Timestamp(et.date())

    # First gate: check if market is open today (handles holidays/weekends)
    if not nyse.is_session(session_label):
        return Session.CLOSED

    # Check for early close (any close before 4:00 PM ET)
    POST_START = 16 * 60  # Default: 4:00 PM ET = 960 minutes
    try:
        session_close = nyse.session_close(session_label)
        session_close_et = session_close.tz_convert("America/New_York")
        # Any close before 4:00 PM is an early close
        if session_close_et.hour < 16:
            POST_START = session_close_et.hour * 60 + session_close_et.minute
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        # If we can't determine close time, assume regular hours (4:00 PM)
        logger.warning(
            "Could not determine session close time for "
            f"{session_label}, falling back to 16:00 ET: {exc}"
        )

    # Calculate minutes since midnight for time-based classification
    minutes = et.hour * 60 + et.minute

    # Define session boundaries in minutes since midnight ET
    PRE_START = 4 * 60  # 04:00 ET = 240 minutes
    REG_START = 9 * 60 + 30  # 09:30 ET = 570 minutes
    POST_END = 20 * 60  # 20:00 ET = 1200 minutes

    # Classify based on ET time
    if PRE_START <= minutes < REG_START:
        return Session.PRE
    elif REG_START <= minutes < POST_START:
        return Session.REG
    elif POST_START <= minutes < POST_END:
        return Session.POST
    else:
        return Session.CLOSED
