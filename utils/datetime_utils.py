"""Datetime helpers for UTC normalization and conversion."""

from datetime import UTC, datetime


def normalize_to_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    - If `dt` is naive, attach UTC tzinfo.
    - If `dt` is aware, convert to UTC via `astimezone`.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_rfc3339(timestamp_str: str) -> datetime:
    """Parse RFC3339/ISO 8601 timestamp string to UTC datetime.

    Handles common Z/offset/naive formats and normalizes to UTC.
    """
    if not isinstance(timestamp_str, str):
        raise TypeError(f"timestamp_str must be str, got {type(timestamp_str).__name__}")

    if timestamp_str.endswith("Z"):
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    elif "+" in timestamp_str or timestamp_str.count("-") > 2:
        dt = datetime.fromisoformat(timestamp_str)
    else:
        # Assume UTC if no timezone info present
        dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=UTC)

    return normalize_to_utc(dt)
