# LLM Providers — Parameter Cheatsheet

## OpenAIProvider

### Constructor Fields
- **`settings: OpenAISettings`** — holds your API key loaded from env.  
  `OpenAIProvider(..., settings=OpenAISettings.from_env(), ...)`

- **`model_name: str`** — any Responses-capable model (e.g., `"o4-mini"`, `"gpt-4o"`, `"gpt-5"`).  
  `OpenAIProvider(..., model_name="o4-mini", ...)`

- **`temperature: float | None`** — randomness control; `0` = deterministic, higher = more diverse.  
  `OpenAIProvider(..., temperature=0.2, ...)`

- **`reasoning: dict | None`** — reasoning effort.  
  Allowed: `{"effort": "minimal" | "low" | "medium" | "high"}`  
  Defaults: If omitted, the provider sets `{"effort":"low"}` to balance cost with tool compatibility.  
  `OpenAIProvider(..., reasoning={"effort":"medium"}, ...)`

- **`tools: list[dict] | None`** — enable built-ins or custom function tools.  
  - **`{"type":"web_search"}`** — search the live web and return cited results.  
    `tools=[{"type":"web_search"}]`
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

- **`**kwargs -> self.config`** — extra params for `responses.create(...)`.  
  - `max_output_tokens: int` — max tokens in output.  
    `..., max_output_tokens=8000`  
  - `top_p: float` — nucleus sampling (0–1).  
    `..., top_p=0.9`  
  - `presence_penalty: float` — discourage repeats (0–2).  
    `..., presence_penalty=0.1`  
  - `frequency_penalty: float` — lower freq of common tokens (0–2).  
    `..., frequency_penalty=0.2`

### Call
`text = await openai_llm.generate("Write 3 bullets.")`

---

## GeminiProvider

### Constructor Fields
- **`settings: GeminiSettings`** — holds your API key loaded from env.  
  `GeminiProvider(..., settings=GeminiSettings.from_env(), ...)`

- **`model_name: str`** — e.g., `"gemini-2.5-flash"`, `"gemini-2.5-pro"`.  
  `GeminiProvider(..., model_name="gemini-2.5-flash", ...)`

- **`temperature: float | None`** — randomness control.  
  `GeminiProvider(..., temperature=0.7, ...)`

- **`tools: list | None`** — declare capabilities (dict forms shown).  
  - **Code execution** — run Python for math, data wrangling, small files.  
    `tools=[{"code_execution":{}}]`
  - **Google search** — grounded web search with citations.  
    `tools=[{"google_search":{}}]`
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
  - `thinking_budget: int` — max tokens for “thinking” phase.  
  - `include_thoughts: bool` — include a summary of thoughts in output.  
  Defaults: If omitted, the provider sets a small budget (`{"thinking_budget": 128}`) to enable lightweight reasoning while limiting cost.  
  `GeminiProvider(..., thinking_config={"thinking_budget":2048,"include_thoughts":False}, ...)`

- **`**kwargs -> self.config`** — passed into `GenerateContentConfig(...)`.  
  - `candidate_count: int` — number of completions to return.  
    `..., candidate_count=1`  
  - **Function-calling control:**  
    `tool_config={"function_calling_config":{"mode":"ANY" | "NONE"}}`  
    `automatic_function_calling={"disable": True | False}`  
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
    model_name="gpt-5",
    temperature=0.3,
    reasoning={"effort":"medium"},
    tools=[{"type":"code_interpreter","container":{"type":"auto"}}],
    tool_choice="auto",
    max_output_tokens=2000
)
text = await openai_llm.generate("Calculate 392817 * 74837291")
```
### Gemini
```python
gemini = GeminiProvider(
    settings=GeminiSettings.from_env(),
    model_name="gemini-2.5-flash",
    temperature=0.7,
    tools=[{"code_execution":{}},{"url_context":{}}],  # no tool_choice with code-exec only
    thinking_config={"thinking_budget":1024},
    response_mime_type="text/markdown"
)
text = await gemini.generate("Summarize feature X in 5 bullets.")
```

### Gemini Tool Choice + Code Execution (Gotcha)
- If your `tools` include only `{"code_execution":{}}`, do not set `tool_choice`.
- `tool_choice` controls function calling. It requires `function_declarations` to be present.
- If you set `tool_choice` without functions, the API may return INVALID_ARGUMENT.

---

## Using Settings for API Keys (Recommended)

Instead of managing API keys directly, you can use the settings modules from `config/llm/`:

### OpenAI with Settings (required)
```python
from dotenv import load_dotenv
from config.llm.openai import OpenAISettings
from llm.providers.openai import OpenAIProvider

# Load environment variables (only at entry points/tests)
load_dotenv(override=True)

# Create settings from environment
settings = OpenAISettings.from_env()

# Pass settings object into provider
openai_llm = OpenAIProvider(
    settings=settings,
    model_name="gpt-5",
    temperature=0.3
)
text = await openai_llm.generate("Your prompt here")
```

### Gemini with Settings (required)
```python
from dotenv import load_dotenv
from config.llm.gemini import GeminiSettings
from llm.providers.gemini import GeminiProvider

# Load environment variables (only at entry points/tests)
load_dotenv(override=True)

# Create settings from environment
settings = GeminiSettings.from_env()

# Pass settings object into provider
gemini_llm = GeminiProvider(
    settings=settings,
    model_name="gemini-2.5-flash",
    temperature=0.7
)
text = await gemini_llm.generate("Your prompt here")
```

### Environment Variables
- **OpenAI**: Set `OPENAI_API_KEY` in your `.env` file or environment
- **Gemini**: Set `GEMINI_API_KEY` in your `.env` file or environment

Both settings classes validate that API keys are present and non-empty, raising `ValueError` if missing.
