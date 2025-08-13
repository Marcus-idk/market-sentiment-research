import asyncio
import os
import sys
from pathlib import Path
import base64
import hashlib
import re

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from llm import OpenAIProvider, GeminiProvider

load_dotenv(override=True)

# Helper functions for hash testing
def make_base64_blob(n_bytes=64):
    blob = os.urandom(n_bytes)
    b64 = base64.b64encode(blob).decode("ascii")
    sha = hashlib.sha256(blob).hexdigest()
    return b64, sha

def extract_hex64(s: str) -> str:
    m = re.search(r"\b[0-9a-fA-F]{64}\b", s)
    return m.group(0).lower() if m else ""

# Tests

async def test_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Skipping OpenAI test - no API key")
        return
    
    provider = OpenAIProvider(api_key=api_key, model_name="gpt-5")
    assert await provider.validate_connection()
    
    response = await provider.generate("Say 'test successful'")
    assert len(response) > 0
    print("OpenAI: Connection Good")

async def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Skipping Gemini test - no API key")
        return
    
    provider = GeminiProvider(api_key=api_key, model_name="gemini-2.5-flash")
    assert await provider.validate_connection()
    
    response = await provider.generate("Say 'test successful'")
    assert len(response) > 0
    print("Gemini: Connection Good")


async def test_openai_tools_hash():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Skipping OpenAI tools-hash test - no API key")
        return

    b64, expected_sha = make_base64_blob(4)
    prompt = (
        "Decode the following base64 to raw bytes and compute its SHA-256.\n"
        "Return only the 64-character lowercase hex digest, no spaces or text.\n\n"
        "```base64\n" + b64 + "\n```"
    )

    # With tools
    provider_with_tools = OpenAIProvider(
        api_key=api_key,
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

async def test_gemini_tools_hash():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Skipping Gemini tools-hash test - no API key")
        return

    b64, expected_sha = make_base64_blob(4)
    prompt = (
        "Decode the following base64 to raw bytes and compute its SHA-256.\n"
        "Return only the 64-character lowercase hex digest, no spaces or text.\n\n"
        "```base64\n" + b64 + "\n```"
    )

    # With code execution
    provider_with_tools = GeminiProvider(
        api_key=api_key,
        model_name="gemini-2.5-flash",
        tools=[{"code_execution": {}}],
        tool_choice="auto"
    )
    out_with_tools = await provider_with_tools.generate(prompt)

    ok_with_tools = expected_sha == extract_hex64(out_with_tools)

    if ok_with_tools:
        print("Gemini: Code execution working correctly (SHA-256 test)")
    else:
        print("Gemini: Code execution may not be working")

if __name__ == "__main__":
    asyncio.run(test_openai())
    asyncio.run(test_gemini())
    asyncio.run(test_openai_tools_hash())
    asyncio.run(test_gemini_tools_hash())