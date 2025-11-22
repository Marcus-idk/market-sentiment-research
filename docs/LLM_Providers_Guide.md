# LLM Providers — Parameter Cheatsheet

## OpenAIProvider

### Constructor Fields
- **`settings: OpenAISettings`** — holds your API key loaded from env.  
  `OpenAIProvider(..., settings=OpenAISettings.from_env(), ...)`

- **`model_name: str`** — any Responses-capable model (for example, the latest GPT-series text or reasoning model).  
  `OpenAIProvider(..., model_name="<gpt-model-name>", ...)`

- **`temperature: float | None`** — randomness control; `0` = deterministic, higher = more diverse.  
  - Supported range: `0.0–2.0`, default is `1.0` when omitted.  
  - For some reasoning models, temperature may be fixed at `1.0` even if you pass a value.  
  `OpenAIProvider(..., temperature=0.2, ...)`

- **`reasoning: dict | None`** — reasoning effort.
  - Allowed: `{"effort": "low" | "medium" | "high"}` on reasoning models (e.g., newer GPT reasoning variants).  
  - On non‑reasoning models this may be ignored or rejected by the API.  
  Defaults: If omitted, the provider sets `{"effort":"low"}` to balance cost with tool compatibility.
  `OpenAIProvider(..., reasoning={"effort":"medium"}, ...)`

- **`tools: list[dict] | None`** — enable built-ins or custom function tools.
  - **`{"type":"web_search"}`** — search the live web and return cited results.
    `tools=[{"type":"web_search"}]`
    **Note:** Some SDKs still expose preview types like `web_search_preview`; if your SDK lacks `web_search`, use the preview name.
  - **`{"type":"file_search"}`** — retrieve answers from uploaded files/vector stores.  
    `tools=[{"type":"file_search"}]`
  - **`{"type":"code_interpreter"}`** — run Python for calculations, parsing, plots, file ops.  
    `tools=[{"type":"code_interpreter","container":{"type":"auto"}}]`
  - **`{"type":"computer_use"}`** — control a virtual desktop (click/type/navigate apps/sites).  
    `tools=[{"type":"computer_use"}]`
  - **Function tool** — call your own function with JSON arguments you define.  
    `tools=[{"type":"function","function":{"name":"save","description":"...","parameters":{...}}}]`

- **`tool_choice: str | dict | None`** — control tool usage.
  - **`"auto"`** — model decides if/when to call any allowed tool.
    `tool_choice="auto"`
  - **`"none"`** — disable all tool calls.
    `tool_choice="none"`
  - **Force specific tool** — only call the one you specify.
    `tool_choice={"type":"function","function":{"name":"save"}}`
  - **Newer GPT-series caveat:** Many of the latest GPT reasoning models currently support only `tool_choice="auto"`. Officially supported choices are `"auto"`, `"none"`, and (in some flows) `"required"`. The provider automatically coerces string values like `"none"` or `"required"` to `"auto"` **only for models we explicitly special-case in code (currently names starting with `"gpt-5"`)**. For other models, you must check the model docs and set a safe `tool_choice` yourself.

- **`**kwargs -> self.config`** — extra params for `responses.create(...)`.
  - `max_completion_tokens: int` — preferred over `max_tokens`; upper bound for generated tokens (including reasoning tokens).  
    `..., max_completion_tokens=8000`
  - `top_p: float` — nucleus sampling (0–1, default 1.0). Use lower values (e.g. 0.1) to constrain diversity.
    `..., top_p=0.9`
  - Other Responses‑API fields (audio, images, etc.) can also be passed through this dict as needed.

### Call
`text = await openai_llm.generate("Write 3 bullets.")`

---

## GeminiProvider

### Constructor Fields
- **`settings: GeminiSettings`** — holds your API key loaded from env.  
  `GeminiProvider(..., settings=GeminiSettings.from_env(), ...)`

- **`model_name: str`** — any supported Gemini text or reasoning model.  
  `GeminiProvider(..., model_name="<gemini-model-name>", ...)`

- **`temperature: float | None`** — randomness control.  
  - Supported range: `0.0–2.0`.  
  `GeminiProvider(..., temperature=0.7, ...)`

- **`tools: list | None`** — declare capabilities (dict forms shown).
  - **Code execution** — run Python for math, data wrangling, small files.
    `tools=[{"code_execution":{}}]`
  - **Google Search retrieval** — search the web and return grounded results.
    `tools=[{"google_search_retrieval":{}}]`
  - **URL context** — fetch and read content from given URLs.  
    `tools=[{"url_context":{}}]`
  - **Function declarations** — expose callable functions; you handle execution.  
    `tools=[{"function_declarations":[{"name":"save","description":"...","parameters":{...}}]}]`

- **`tool_choice: str | None`** — control tool usage.  
  - **`"auto"`** — model decides if/when to call any allowed tool.  
    `tool_choice="auto"`
  - **`"none"`** — disable all tool calls.  
    `tool_choice="none"`
  - **`"any"`** — force at least one tool call (requires tools to be provided).  
    `tool_choice="any"`

- **`thinking_config: dict | None`** — reasoning controls.  
  - Used only for Gemini “thinking” / reasoning models.  
  - Typical fields (depending on model/version):  
    - `thinking_budget_token_limit: int` — max tokens for the internal thinking phase.  
    - `include_thoughts: bool` — whether to include a summarized thought trace in the response.  
  Defaults: If omitted, the provider sets a small budget (e.g., `{"thinking_budget": 128}` when supported) to enable lightweight reasoning while limiting cost.  
  `GeminiProvider(..., thinking_config={"thinking_budget_token_limit":2048,"include_thoughts":False}, ...)`

- **`**kwargs -> self.config`** — passed into `GenerateContentConfig(...)`.
  - `candidate_count: int` — number of completions to return.
    `..., candidate_count=1`
  - **Function-calling control:**
    `tool_config={"function_calling_config":{"mode":"ANY" | "NONE"}}`
    Note: Only applies when you pass `function_declarations` in `tools`. If you use only `{"code_execution":{}}`, leave `tool_choice` unset; setting it can cause INVALID_ARGUMENT.
  - **Structured output:**  
    `response_mime_type="application/json"`  
    `response_schema={"type":"object","properties":{...},"required":[...]}`  
  - **Safety:**  
    `safety_settings=[{"category":"HARM_CATEGORY_...","threshold":"BLOCK_NONE|..."}]`

### Call
`text = await gemini.generate("Give 3 test ideas.")`

---

## Minimal 2-Step Patterns

### OpenAI
```python
openai_llm = OpenAIProvider(
    settings=OpenAISettings.from_env(),
    model_name="<gpt-model-name>",
    temperature=0.3,
    reasoning={"effort":"medium"},
    tools=[{"type":"code_interpreter","container":{"type":"auto"}}],
    tool_choice="auto",
    max_completion_tokens=2000
)
text = await openai_llm.generate("Calculate 392817 * 74837291")
```
### Gemini
```python
gemini = GeminiProvider(
    settings=GeminiSettings.from_env(),
    model_name="<gemini-model-name>",
    temperature=0.7,
    tools=[{"code_execution":{}},{"url_context":{}}],  # no tool_choice with code-exec only
    thinking_config={"thinking_budget_token_limit":1024},
    response_mime_type="text/markdown"
)
text = await gemini.generate("Summarize feature X in 5 bullets.")
```

### Gemini Tool Choice + Code Execution (Gotcha)
- If your `tools` include only `{"code_execution":{}}`, do not set `tool_choice`.
- `tool_choice` controls function calling. It requires `function_declarations` to be present.
- If you set `tool_choice` without functions, the API may return INVALID_ARGUMENT.

---

## Structured JSON Output

Both providers support strict JSON output with schema validation. Use these when you need the model to return structured data that conforms to a specific format.

### OpenAI JSON Schema
Use `response_format` with `type: "json_schema"` to enforce a JSON schema (Responses API):

```python
from config.llm.openai import OpenAISettings
from llm.providers.openai import OpenAIProvider

openai_llm = OpenAIProvider(
    settings=OpenAISettings.from_env(),
    model_name="<gpt-model-name>",
    temperature=0.3,
    # Pass json_schema config via **kwargs
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "stock_analysis",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "recommendation": {"type": "string", "enum": ["BUY", "HOLD", "SELL"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["ticker", "recommendation", "confidence"]
            }
        }
    }
)
response = await openai_llm.generate("Analyze AAPL stock")
# Response will be valid JSON matching the schema
```

### Gemini JSON Schema
Use `response_mime_type` and `response_schema` in kwargs:

```python
from config.llm.gemini import GeminiSettings
from llm.providers.gemini import GeminiProvider

gemini_llm = GeminiProvider(
    settings=GeminiSettings.from_env(),
    model_name="<gemini-model-name>",
    temperature=0.3,
    # Pass via **kwargs to GenerateContentConfig
    response_mime_type="application/json",
    response_schema={
        "type": "OBJECT",
        "properties": {
            "ticker": {"type": "STRING"},
            "recommendation": {"type": "STRING", "enum": ["BUY", "HOLD", "SELL"]},
            "confidence": {"type": "NUMBER"}
        },
        "required": ["ticker", "recommendation", "confidence"]
    }
)
response = await gemini_llm.generate("Analyze AAPL stock")
# Response will be valid JSON matching the schema
```

**Note:** Both providers support a limited JSON Schema subset. Avoid advanced features like `allOf`, `oneOf`, `not` for best compatibility.

---

## Knobs, Tools, and Recent Changes (Cheatsheet)

### OpenAI — Supported Knobs & Gotchas
- `temperature`: `0.0–2.0`, defaults to `1.0`. Reasoning models may fix it at `1.0`.
- `top_p`: `0.0–1.0`, defaults to `1.0`. Use low values (e.g., `0.1`) for very focused outputs.
- `max_completion_tokens`: preferred limit knob; `max_tokens` is deprecated.
- `reasoning.effort`: `low|medium|high` on reasoning models only.
- Reasoning models may not support classic system messages; use the appropriate “developer” role or equivalent in higher‑level APIs when needed.

### Gemini — Supported Knobs & Gotchas
- `temperature`: `0.0–2.0` to control randomness.
- `topP`: `0.0–1.0` nucleus sampling; `topK` (int) is also available.
- `maxOutputTokens`: integer limit for response length (exposed as `max_output_tokens` / similar in some SDKs).
- `thinking_config`: only for thinking/reasoning models; fields like `include_thoughts` and `thinking_budget_token_limit` may vary by version.
- Safety: default settings can be strict; setting thresholds like `BLOCK_ONLY_HIGH` often reduces over‑blocking for benign prompts.

### Tools Summary
- **OpenAI tools:** `function`, `web_search_preview`, `file_search`, `code_interpreter`, `computer_use_preview` (availability depends on access).  
  Use `tools=[...]` plus `tool_choice="auto" | "none" | "required" | {type:function...}`.
- **Gemini tools:** `function_declarations`, `google_search_retrieval`, `code_execution`, `url_context`.  
  Use `tools=[...]` plus `tool_config={"function_calling_config":{"mode":"AUTO"|"ANY"|"NONE"}}` when using functions.

### Recent API Shape Changes (High Level)
- OpenAI Responses API replaces older `/v1/chat/completions`; `max_completion_tokens` and `response_format` are preferred over legacy knobs.
- Gemini places structured output fields under `generationConfig` in the wire format; the Python SDK exposes them as `GenerateContentConfig` fields (e.g., `response_mime_type`, `response_schema`).

---
