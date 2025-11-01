"""Contract tests for LLM code execution tooling."""

from __future__ import annotations

import pytest

from tests.integration.llm.helpers import extract_hex64, make_base64_blob

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_code_tools_enabled_matches_expected_digest(provider_spec):
    provider = provider_spec.make_provider_for_code_tools(enabled=True)
    b64, expected_sha = make_base64_blob(4)
    prompt = (
        "Decode the following base64 to raw bytes and compute its SHA-256.\n"
        "Return only the 64-character lowercase hex digest, no spaces or text.\n\n"
        "```base64\n"
        f"{b64}\n"
        "```"
    )

    response = await provider.generate(prompt)
    digest = extract_hex64(response)

    assert digest == expected_sha


async def test_code_tools_disabled_does_not_match_digest(provider_spec):
    provider = provider_spec.make_provider_for_code_tools(enabled=False)
    b64, expected_sha = make_base64_blob(4)
    prompt = (
        "Decode the following base64 to raw bytes and compute its SHA-256.\n"
        "Return only the 64-character lowercase hex digest, no spaces or text.\n\n"
        "```base64\n"
        f"{b64}\n"
        "```"
    )

    response = await provider.generate(prompt)
    digest = extract_hex64(response)

    assert digest != expected_sha
