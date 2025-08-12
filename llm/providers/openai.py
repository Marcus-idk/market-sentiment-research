from openai import AsyncOpenAI
from typing import Optional, Union, List, Dict
from ..base import LLMProvider


class OpenAIProvider(LLMProvider):
    
    def __init__(
        self,
        api_key: str,
        model_name: str,
        temperature: Optional[float] = None,
        reasoning: Optional[Dict] = None,  # e.g. {"effort": "medium"}
        tools: Optional[List[Dict]] = None,  # e.g. [{"type":"web_search"}] or function tools
        tool_choice: Optional[Union[str, Dict]] = None,  # "auto" | {"type":"auto", ...}
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.model_name = model_name
        self.temperature = temperature
        self.reasoning = reasoning
        self.tools = tools
        self.tool_choice = tool_choice
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate(self, prompt: str) -> str:
        args = {
            "model": self.model_name,
            "input": prompt,  # Responses API
            "temperature": self.temperature,
            **self.config
        }
        
        if self.reasoning:
            args["reasoning"] = self.reasoning  # {"effort": "low|medium|high"}
        if self.tools:
            args["tools"] = self.tools  # built-in & function tools
        if self.tool_choice:
            args["tool_choice"] = self.tool_choice  # e.g. {"type":"auto"}

        resp = await self.client.responses.create(**args)
        return resp.output_text
    
    async def validate_connection(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False