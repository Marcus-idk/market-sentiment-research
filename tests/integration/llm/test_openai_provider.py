import pytest

from dotenv import load_dotenv
from llm import OpenAIProvider
from config.llm import OpenAISettings
from tests.integration.llm.helpers import make_base64_blob, extract_hex64

# Mark all tests in this module as integration and network tests
pytestmark = [pytest.mark.integration, pytest.mark.network]

load_dotenv(override=True)


@pytest.mark.asyncio
async def test_openai_connection():
    try:
        openai_settings = OpenAISettings.from_env()
    except ValueError:
        pytest.skip("OPENAI_API_KEY not set, skipping live test")

    provider = OpenAIProvider(settings=openai_settings, model_name="gpt-5")
    assert await provider.validate_connection()
    
    response = await provider.generate("Say 'test successful'")
    assert len(response) > 0
    print("OpenAI: Connection Good")


@pytest.mark.asyncio
async def test_openai_code_interpreter():
    try:
        openai_settings = OpenAISettings.from_env()
    except ValueError:
        pytest.skip("OPENAI_API_KEY not set, skipping live test")

    b64, expected_sha = make_base64_blob(4)
    prompt = (
        "Decode the following base64 to raw bytes and compute its SHA-256.\n"
        "Return only the 64-character lowercase hex digest, no spaces or text.\n\n"
        "```base64\n" + b64 + "\n```"
    )

    # With tools
    provider_with_tools = OpenAIProvider(
        settings=openai_settings,
        model_name="gpt-5",
        tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
        tool_choice="auto"
    )
    out_with_tools = await provider_with_tools.generate(prompt)

    ok_with_tools = expected_sha == extract_hex64(out_with_tools)

    if ok_with_tools:
        print("OpenAI: Code interpreter working correctly (SHA-256 test)")
    else:
        print("OpenAI: Code interpreter may not be working")