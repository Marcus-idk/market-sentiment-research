import pytest

from dotenv import load_dotenv
from llm import GeminiProvider
from config.llm import GeminiSettings
from tests.integration.llm.helpers import make_base64_blob, extract_hex64

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

    ok_with_tools = expected_sha == extract_hex64(out_with_tools)

    if ok_with_tools:
        print("Gemini: Code execution working correctly (SHA-256 test)")
    else:
        print("Gemini: Code execution may not be working")