import pytest
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from llm import GeminiProvider
from config.llm import GeminiSettings
from tests.integration.llm.helpers import make_base64_blob, extract_hex64, fetch_featured_wiki, normalize_title

# Mark all tests in this module as integration and network tests
pytestmark = [pytest.mark.integration, pytest.mark.network]

load_dotenv(override=True)

@pytest.mark.asyncio
async def test_gemini_connection():
    try:
        gemini_settings = GeminiSettings.from_env()
    except ValueError:
        pytest.skip("GEMINI_API_KEY not set, skipping live test")

    provider = GeminiProvider(settings=gemini_settings, model_name="gemini-2.5-flash")
    assert await provider.validate_connection()
    
    response = await provider.generate("Say 'test successful'")
    assert len(response) > 0
    print("Gemini: Connection Good")


@pytest.mark.asyncio
async def test_gemini_code_execution():
    try:
        gemini_settings = GeminiSettings.from_env()
    except ValueError:
        pytest.skip("GEMINI_API_KEY not set, skipping live test")

    b64, expected_sha = make_base64_blob(4)
    prompt = (
        "Decode the following base64 to raw bytes and compute its SHA-256.\n"
        "Return only the 64-character lowercase hex digest, no spaces or text.\n\n"
        "```base64\n" + b64 + "\n```"
    )

    # With code execution
    provider_with_tools = GeminiProvider(
        settings=gemini_settings,
        model_name="gemini-2.5-flash",
        tools=[{"code_execution": {}}]
    )
    out_with_tools = await provider_with_tools.generate(prompt)
    digest_with_tools = extract_hex64(out_with_tools)
    assert expected_sha == digest_with_tools, f"with tools: expected {expected_sha}, got {digest_with_tools}"

    # Without tools (negative check)
    provider_no_tools = GeminiProvider(
        settings=gemini_settings,
        model_name="gemini-2.5-flash"
    )
    out_no_tools = await provider_no_tools.generate(prompt)
    digest_no_tools = extract_hex64(out_no_tools)
    assert expected_sha != digest_no_tools, "without tools: digest unexpectedly matched expected SHA"


@pytest.mark.asyncio
async def test_gemini_web_search():
    try:
        gemini_settings = GeminiSettings.from_env()
    except ValueError:
        pytest.skip("GEMINI_API_KEY not set, skipping live test")

    # Get yesterday's date in UTC
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    
    # Fetch yesterday's Wikipedia featured article
    expected_title = await fetch_featured_wiki(yesterday_utc)
    normalized_expected = normalize_title(expected_title)
    
    prompt = (
        f"What was Wikipedia's featured article on {yesterday_utc.strftime('%B %d, %Y')}? "
        "Return just the article title."
    )
    
    # With Google search
    provider_with_search = GeminiProvider(
        settings=gemini_settings,
        model_name="gemini-2.5-flash",
        tools=[{"google_search": {}}]
    )
    response_with_search = await provider_with_search.generate(prompt)
    normalized_response = normalize_title(response_with_search)
    
    # Check if the expected title is in the response
    assert normalized_expected in normalized_response, (
        f"with Google search: expected '{expected_title}' not found in response"
    )
    
    # Without web search (negative check)
    provider_no_search = GeminiProvider(
        settings=gemini_settings,
        model_name="gemini-2.5-flash"
    )
    response_no_search = await provider_no_search.generate(prompt)
    normalized_no_search = normalize_title(response_no_search)
    
    # Should NOT find the correct title without web search
    assert normalized_expected not in normalized_no_search, (
        "without web search: unexpectedly found correct title"
    )
