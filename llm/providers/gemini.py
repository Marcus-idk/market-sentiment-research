from google import genai
from google.genai import types
from typing import Optional, List, Dict
from ..base import LLMProvider


class GeminiProvider(LLMProvider):
    
    def __init__(
        self,
        api_key: str,
        model_name: str,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict]] = None,
        thinking_config: Optional[Dict] = None,
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.model_name = model_name
        self.temperature = temperature
        self.tools = tools
        self.thinking_config = thinking_config
        self.client = genai.Client(api_key=api_key)

    async def generate(self, prompt: str) -> str:
        cfg = {
            "temperature": self.temperature,
            "candidate_count": 1,
            **self.config
        }
        
        if self.tools:
            cfg["tools"] = self.tools
        if self.thinking_config:
            cfg["thinking_config"] = types.ThinkingConfig(**self.thinking_config)

        config = types.GenerateContentConfig(**cfg)
        resp = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return resp.text

    async def validate_connection(self) -> bool:
        try:
            await self.client.aio.models.list()
            return True
        except Exception:
            return False