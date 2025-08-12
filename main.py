import asyncio
import os
from dotenv import load_dotenv
from llm import OpenAIProvider, GeminiProvider

load_dotenv(override=True)

async def main():
    # Test OpenAI with all parameters
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        openai = OpenAIProvider(
            api_key=openai_key, 
            model_name="gpt-5", 
            temperature=1,
            reasoning={"effort": "medium"},
            tools=[{"type": "web_search"}],
            tool_choice="auto"
        )
        response = await openai.generate("what is the rotten tomatoes score for the thunderbolts?")
        print(f"OpenAI: {response}")
    
    # Test Gemini with all parameters
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        gemini = GeminiProvider(
            api_key=gemini_key,
            model_name="gemini-2.5-flash", 
            temperature=0.7,
            tools=[{"code_execution": {}}],
            thinking_config={"thinking_budget": 2048}
        )
        response = await gemini.generate("can u solve 9382928 * 3922202")
        print(f"Gemini: {response}")

if __name__ == "__main__":
    asyncio.run(main())