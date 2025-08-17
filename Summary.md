# TradingBot Codebase Summary

## Technical Stack
- **Python** - Core language for financial libraries and LLM integrations
- **Async/Await** - For concurrent API calls to multiple data sources
- **GitHub Actions** - Data polling every 5 minutes + LLM analysis every 30 minutes
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

### data/ - Data Collection Module

#### __init__.py
Purpose: Clean exports for data collection components.

Exports:
- `DataSource` - Abstract base class for all data providers
- `NewsDataSource` - Abstract base class for news content providers
- `PriceDataSource` - Abstract base class for price/market data providers
- `NewsItem` - Data model for news articles
- `PriceData` - Data model for financial price/market data

#### base.py
Purpose: Abstract base class defining the contract for all data source providers.

Classes:
- `DataSource` - Abstract base class with shared functionality and input validation
- `NewsDataSource` - Abstract base class for news providers (inherits from DataSource)
- `PriceDataSource` - Abstract base class for price data providers (inherits from DataSource)
- `DataSourceError` - Base exception for data source related errors
- `RateLimitError` - Exception for API rate limit exceeded scenarios

Functions:
- `fetch_incremental(since)` - Fetch new data since timestamp (async, returns typed models)
  - NewsDataSource returns List[NewsItem]
  - PriceDataSource returns List[PriceData]
- `validate_connection()` - Test if data source is reachable (async, returns bool)
- `update_last_fetch_time(timestamp)` - Update last successful fetch timestamp
- `get_last_fetch_time()` - Get last successful fetch timestamp

Input Validation:
- Constructor validates source_name (non-empty string, max 100 chars)
- update_last_fetch_time validates timestamp (not None, not future, proper type)
- Comprehensive error messages for debugging

#### models.py
Purpose: Data Transfer Objects (DTOs) for standardized data representation across all providers.

Classes:
- `NewsItem` - Data model for news articles from various sources
  - Required fields: title, content, timestamp, source
  - Optional fields: url, author, tags, unique_id, raw_data
  - Input validation in __post_init__ (non-empty strings, proper datetime type)
- `PriceData` - Data model for financial price/market data from various sources
  - Required fields: symbol, price (Decimal), timestamp
  - Optional fields: volume, market, data_type, currency, 24h data, change percentages
  - Input validation in __post_init__ (non-empty symbol, Decimal price, non-negative volume)

Features:
- Uses @dataclass for clean field definitions and automatic methods
- Raw data preservation for debugging and audit trails
- Comprehensive validation to catch data quality issues early

Design Choices:
- **Decimal vs Float**: Critical distinction for financial data integrity
  - Decimal: Used for all money amounts (price, high_24h, low_24h, change_24h) to prevent floating-point rounding errors that could affect financial calculations
  - Float: Used for ratios and scores (sentiment_score, change_percent_24h) where minor precision loss is acceptable
  - Example: `0.1 + 0.2 == 0.3` is False with float, True with Decimal

#### API_Reference.md
Purpose: Comprehensive documentation of 5 data source APIs for trading bot integration.

Data Sources Documented:
- **Finnhub API** - Primary financial data (60 calls/min free, stocks + crypto + news)
- **Polygon.io API** - Enhanced market data backup (5 calls/min free, batch requests)
- **RSS Feeds** - Free news aggregation (no limits, multiple financial sources)
- **Reddit API (PRAW)** - Social sentiment analysis (100 queries/min free)
- **SEC EDGAR API** - Official regulatory filings (10 req/sec free, stocks only)

Technical Details:
- Rate limits and cost analysis for each API
- Data coverage (stocks vs crypto) per source
- Implementation strategies and polling schedules
- 5-minute polling architecture with usage calculations