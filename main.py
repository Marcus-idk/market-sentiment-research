import asyncio
import os
from dotenv import load_dotenv
from llm import OpenAIProvider, GeminiProvider

load_dotenv(override=True)

async def main():
    # Test OpenAI with reasoning
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        openai = OpenAIProvider(
            api_key=openai_key, 
            model_name="gpt-5", 
            temperature=1,
            reasoning={"effort": "medium"}
        )
        response = await openai.generate("What model are you and can you use reasoning?")
        print(f"OpenAI: {response}")
    
    # Test Gemini with thinking config
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        gemini = GeminiProvider(
            api_key=gemini_key, 
            model_name="gemini-2.5-flash", 
            temperature=0.7,
            thinking_config={"thinking_budget": 1024}
        )
        response = await gemini.generate("What model are you and can you think deeply?")
        print(f"Gemini: {response}")

if __name__ == "__main__":
    asyncio.run(main())