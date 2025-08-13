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
- `__init__(api_key, **kwargs)` - Base class constructor for all providers
- Individual providers extend with specific parameters (model_name, temperature, reasoning, tools, thinking_config)

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
- `tool_choice` - Control tool usage (none/auto/any modes)
- `thinking_config` - Control thinking behavior with thinking_budget parameter

#### llm-providers-guide.md
Purpose: Developer reference documentation for LLM provider configuration and usage.

Features:
- Parameter cheatsheets for OpenAI and Gemini providers
- Constructor field documentation with examples
- Minimal usage patterns and code examples
- Tool configuration guides (web_search, code_execution, reasoning, etc.)

### tests/ - Testing Framework
Purpose: Validate LLM provider functionality and reliability for automated trading system.

#### tests/test_llm_providers.py
Purpose: Basic connectivity and functionality testing for production readiness.

Features:
- Connection validation tests for both OpenAI and Gemini providers
- SHA-256 hash tool validation to verify code execution functionality
- Environment variable validation
- Graceful skipping when API keys are unavailable
- Direct execution support for development workflow

Testing Strategy:
- SHA-256 tool validation tests to ensure code execution works correctly
- Critical for automated financial system reliability
- Foundation for expanded integration testing