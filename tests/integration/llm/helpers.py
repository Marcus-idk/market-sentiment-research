"""Helper functions for LLM integration tests."""

from __future__ import annotations

import base64
import hashlib
import os
import re
from datetime import date

import pytest

from config.retry import DEFAULT_DATA_RETRY
from utils.http import get_json_with_retry

_WIKI_URL = "https://en.wikipedia.org/api/rest_v1/feed/featured/{y}/{m:02d}/{d:02d}"


def make_base64_blob(n_bytes: int = 64) -> tuple[str, str]:
    """Generate a random base64 blob and its SHA-256 hex digest."""
    blob = os.urandom(n_bytes)
    b64 = base64.b64encode(blob).decode("ascii")
    sha = hashlib.sha256(blob).hexdigest()
    return b64, sha


def extract_hex64(s: str) -> str:
    """Extract a 64-character hex string from text, or return empty string."""
    m = re.search(r"\b[0-9a-fA-F]{64}\b", s)
    return m.group(0).lower() if m else ""


async def fetch_featured_wiki(date_utc: date) -> str:
    """Fetch Wikipedia's featured article title for a given date."""
    url = _WIKI_URL.format(y=date_utc.year, m=date_utc.month, d=date_utc.day)

    headers = {"User-Agent": "Information (marcusgohkz@gmail.com)"}

    data = await get_json_with_retry(
        url,
        headers=headers,
        timeout=DEFAULT_DATA_RETRY.timeout_seconds,
        max_retries=DEFAULT_DATA_RETRY.max_retries,
        base=DEFAULT_DATA_RETRY.base,
        mult=DEFAULT_DATA_RETRY.mult,
        jitter=DEFAULT_DATA_RETRY.jitter,
    )

    tfa = (data or {}).get("tfa")
    if not tfa:
        pytest.skip("Wikipedia payload missing 'tfa'")

    # Try multiple fallback paths for title
    titles = tfa.get("titles", {})
    title = (
        titles.get("normalized")
        or titles.get("display")
        or tfa.get("normalizedtitle")
        or tfa.get("title")
    )

    if not title:
        pytest.skip("Wikipedia payload missing title")

    return title


def normalize_title(s: str) -> str:
    """Normalize a title to lowercase alphanumeric for comparison."""
    return "".join(ch.lower() for ch in s if ch.isalnum())
