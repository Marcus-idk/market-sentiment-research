"""Contract tests for LLM web search tooling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.llm.helpers import (
    fetch_featured_wiki,
    normalize_title,
)

pytestmark = [pytest.mark.network, pytest.mark.asyncio]


async def test_web_search_enabled_returns_expected_title(provider_spec):
    provider = provider_spec.make_provider_for_search(enabled=True)
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    expected_title = await fetch_featured_wiki(yesterday_utc)
    normalized_expected = normalize_title(expected_title)
    prompt = (
        f"What was Wikipedia's featured article on {yesterday_utc.strftime('%B %d, %Y')}? "
        "Return just the article title."
    )

    response = await provider.generate(prompt)
    normalized_response = normalize_title(response)

    assert normalized_expected in normalized_response


async def test_web_search_disabled_does_not_find_title(provider_spec):
    provider = provider_spec.make_provider_for_search(enabled=False)
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    expected_title = await fetch_featured_wiki(yesterday_utc)
    normalized_expected = normalize_title(expected_title)
    prompt = (
        f"What was Wikipedia's featured article on {yesterday_utc.strftime('%B %d, %Y')}? "
        "Return just the article title."
    )

    response = await provider.generate(prompt)
    normalized_response = normalize_title(response)

    assert normalized_expected not in normalized_response
