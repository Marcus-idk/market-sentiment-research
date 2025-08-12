# TradingBot Codebase Summary

## Technical Stack
- **Python** - Core language for financial libraries and LLM integrations
- **Async/Await** - For concurrent API calls to multiple data sources
- **GitHub Actions** - Scheduled execution every 30 minutes
- **Environment Variables** - Use `load_dotenv(override=True)` to force reload .env files

## Project Structure

### llm/ - LLM Provider Module

#### __init__.py
Purpose: Clean public API exports for LLM providers.

Exports:
- `LLMProvider` - Abstract base class
- `OpenAIProvider` - OpenAI implementation
- `GeminiProvider` - Google Gemini implementation

#### base.py
Purpose: Abstract base class defining the contract for all LLM providers.

Classes:
- `LLMProvider` - Abstract base with required methods for all providers

Functions:
- `generate(prompt)` - Generate text response from LLM (async, uses config from init)
- `validate_connection()` - Test if provider is properly configured (async, zero-cost)

Constructor:
- `__init__(api_key, model_name, temperature, **kwargs)` - Configure provider behavior once
- Providers accept additional parameters for advanced features (reasoning, tools, thinking_config)

#### providers/ - LLM Provider Implementations
Organization folder for provider implementations (no __init__.py).

##### providers/openai.py
Purpose: OpenAI provider implementation using AsyncOpenAI client.

Classes:
- `OpenAIProvider(LLMProvider)` - Implements OpenAI Responses API with reasoning support

Advanced Features:
- `reasoning` - Enable reasoning with effort levels (low/medium/high)
- `tools` - Built-in tools (web_search) and function calling
- `tool_choice` - Control tool selection behavior

##### providers/gemini.py
Purpose: Google Gemini provider implementation using new unified SDK.

Classes:
- `GeminiProvider(LLMProvider)` - Implements Google Gemini generate content API

Advanced Features:
- `tools` - Function calling and built-in tools integration
- `thinking_config` - Control thinking behavior with thinking_budget parameter

### main.py - Testing Framework
Purpose: Test both LLM providers with their enhanced capabilities.

Features:
- Tests OpenAI reasoning with medium effort level
- Tests Gemini thinking with 1024 token budget
- Validates provider functionality with environment variables