"""Small shared helpers for tools/ scripts."""

import inspect


def clean_docstring(doc: str | None) -> str | None:
    """Return the first non-empty, trimmed line of a docstring, or None."""
    if not doc:
        return None
    cleaned = inspect.cleandoc(doc).strip()
    if not cleaned:
        return None
    return cleaned.splitlines()[0].strip()
