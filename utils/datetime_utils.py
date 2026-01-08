"""Datetime helpers for UTC normalization and conversion."""

from datetime import UTC, datetime


def normalize_to_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    Notes:
        - If `dt` is naive, attach UTC tzinfo.
        - If `dt` is aware, convert to UTC via `astimezone`.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def epoch_seconds_to_utc_datetime(epoch_seconds: object) -> datetime:
    """Convert epoch seconds to a UTC-aware datetime.

    Notes:
        Providers commonly return epoch seconds (ints/floats). This helper
        centralizes the conversion and keeps provider code consistent.
    """
    if not isinstance(epoch_seconds, (int, float)):
        raise TypeError(f"epoch_seconds must be int or float, got {type(epoch_seconds).__name__}")
    return datetime.fromtimestamp(epoch_seconds, tz=UTC)
