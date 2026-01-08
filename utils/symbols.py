"""
Helpers for parsing and filtering symbol lists.

Notes:
    Provides normalization, validation, and filtering helpers for ticker
    symbols.
"""

import logging
import re
from collections.abc import Iterable

logger = logging.getLogger(__name__)

_SYMBOL_PATTERN = re.compile(r"[A-Z][A-Z0-9]{0,4}([.\-][A-Z0-9]{1,2})?$")


def _is_valid_symbol(symbol: str) -> bool:
    """Return True if symbol matches supported exchange ticker formats."""
    return bool(_SYMBOL_PATTERN.fullmatch(symbol))


def normalize_symbol_list(symbols: Iterable[str] | None) -> list[str]:
    """Normalize a symbol list (strip, uppercase, drop empties).

    Notes:
        This helper matches the common provider boundary behavior:
        - trims whitespace
        - uppercases
        - drops empty/whitespace-only entries
        - preserves order (does not dedupe)
    """
    if not symbols:
        return []

    out: list[str] = []
    for sym in symbols:
        if not isinstance(sym, str):
            continue
        cleaned = sym.strip()
        if not cleaned:
            continue
        out.append(cleaned.upper())

    return out


def parse_symbols(
    raw: str | None,
    filter_to: Iterable[str] | None = None,
    *,
    validate: bool = True,
    fail_on_invalid: bool = False,
) -> list[str]:
    """Parse a comma-separated string into a deduplicated list of uppercase symbols.

    Notes:
        Optionally filter to a watchlist and validate shape.
        - Trims/uppercases
        - Deduplicates while preserving order
        - If `filter_to` is provided, returns only symbols present in that set
        - If `validate` is True, enforce common ticker formats (allows
          share-class suffixes)
        - If `fail_on_invalid` is True and validation is enabled, return an
          empty list if any token fails validation
    """

    if not raw or not isinstance(raw, str) or not raw.strip():
        return []

    # Build watchlist filter set for fast lookup
    allow: set[str] | None = None
    if filter_to is not None:
        allow = {s.strip().upper() for s in filter_to if isinstance(s, str) and s.strip()}

    tokens = [s.strip().upper() for s in raw.split(",") if s and s.strip()]

    out: list[str] = []
    seen: set[str] = set()

    for sym in tokens:
        # Skip duplicates
        if sym in seen:
            continue

        # Validate against supported ticker formats (e.g., BRK.B, BF-B, GOOG, PSX)
        if validate and not _is_valid_symbol(sym):
            logger.debug("Unexpected symbol entry format: %s", sym)
            if fail_on_invalid:
                return []
            continue

        # Filter to watchlist if provided
        if allow is not None and sym not in allow:
            continue

        out.append(sym)
        seen.add(sym)

    return out
