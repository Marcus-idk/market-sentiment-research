"""
Helper functions for LLM integration tests.
Focused on testing code execution capabilities of LLM providers.
"""

import os
import base64
import hashlib
import re
from typing import Tuple


def make_base64_blob(n_bytes: int = 64) -> Tuple[str, str]:
    """Generate a random base64 blob and its expected SHA-256 hash.
    
    Used to test LLM code execution tools by having them decode and hash data.
    This validates that the provider can execute code correctly and return results.
    
    Args:
        n_bytes: Number of random bytes to generate (default 64)
        
    Returns:
        Tuple of (base64_string, expected_sha256_hex)
    """
    blob = os.urandom(n_bytes)
    b64 = base64.b64encode(blob).decode("ascii")
    sha = hashlib.sha256(blob).hexdigest()
    return b64, sha


def extract_hex64(s: str) -> str:
    """Extract a 64-character hexadecimal string from LLM response.
    
    LLMs may return the hash embedded in explanatory text. This extracts
    just the hash value for comparison, handling various formatting.
    
    Args:
        s: String potentially containing a SHA-256 hash
        
    Returns:
        Lowercase hex string if found, empty string otherwise
    """
    m = re.search(r"\b[0-9a-fA-F]{64}\b", s)
    return m.group(0).lower() if m else ""