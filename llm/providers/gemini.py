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
        tool_choice: Optional[str] = None,
        thinking_config: Optional[Dict] = None,
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.model_name = model_name
        self.temperature = temperature
        self.tools = tools
        self.tool_choice = tool_choice
        self.thinking_config = thinking_config
        self.client = genai.Client(api_key=api_key)

    async def generate(self, prompt: str) -> str:
        cfg = {
            "candidate_count": 1,
            **self.config
        }
        
        # Only include temperature if not None
        if self.temperature is not None:
            cfg["temperature"] = self.temperature
        
        if self.tools:
            cfg["tools"] = self.tools
            
        if self.tool_choice:
            mode = {"none": "NONE", "auto": "AUTO", "any": "ANY"}.get(str(self.tool_choice).lower())
            if mode:
                # Guard: "any" mode requires tools to be provided
                if mode == "ANY" and not self.tools:
                    raise ValueError("tool_choice='any' requires tools to be provided")
                cfg["tool_config"] = {"function_calling_config": {"mode": mode}}
                    
        if self.thinking_config:
            cfg["thinking_config"] = types.ThinkingConfig(**self.thinking_config)

        config = types.GenerateContentConfig(**cfg)
        resp = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        
        # Check candidates exist before accessing
        if not resp.candidates:
            return ""
        
        # Extract both text and tool outputs
        parts = resp.candidates[0].content.parts
        out = []
        for p in parts:
            if getattr(p, "text", None):
                out.append(p.text)
            if getattr(p, "code_execution_result", None):
                out.append(p.code_execution_result.output or "")
        return "\n".join(out).strip()

    async def validate_connection(self) -> bool:
        try:
            await self.client.aio.models.list()
            return True
        except Exception:
            return False