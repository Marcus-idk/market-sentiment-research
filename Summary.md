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
Purpose: Clean, minimal Data Transfer Objects (DTOs) for v0.2 core functionality.

Classes:
- `NewsItem` - Data model for news articles from various sources
  - Required fields: symbol, url, headline, published (datetime), source
  - Optional fields: content
  - Input validation in __post_init__ (non-empty strings, valid HTTP URLs, timezone handling)
- `PriceData` - Data model for financial price/market data from various sources
  - Required fields: symbol, timestamp (datetime), price (Decimal)
  - Optional fields: volume, is_extended (bool for pre/post-market hours)
  - Input validation in __post_init__ (non-empty symbol, non-negative price/volume, timezone handling)

Features:
- Minimal field set focused on v0.2 requirements (storage + LLM analysis)
- Robust input validation with automatic string trimming and timezone normalization
- URL validation for news items to ensure data quality
- Uses @dataclass for clean field definitions and automatic methods
- Decimal precision for financial data to prevent floating-point errors

#### schema.sql
Purpose: SQLite database schema with expert performance optimizations for 5-minute polling cycles.

Database Architecture:
- **Temporary Raw Data** - 30-minute staging tables deleted after successful LLM processing
- **Persistent Analysis Results** - LLM memory that accumulates and updates over time
- **Failure Recovery** - Raw data preserved if any LLM processing fails

Tables:
- `news_items` - Temporary storage for news articles (PRIMARY KEY: symbol, url)
- `price_data` - Temporary storage for financial price data (PRIMARY KEY: symbol, timestamp_unix)
- `analysis_results` - Persistent LLM analysis results per (symbol, analysis_type) with structured reasoning
- `holdings` - Portfolio tracking with break-even calculations (PRIMARY KEY: symbol)

Expert Optimizations:
- **WAL Mode** - Allows concurrent reads during writes (prevents database locks)
- **Busy Timeout** - 5-second wait instead of instant failure when database busy
- **WITHOUT ROWID** - Performance optimization for natural primary keys
- **URL Normalization** - Strip tracking parameters for cross-provider deduplication
- **Scaled Integers** - Store financial prices as integers (price × 1,000,000) for exact precision
- **Price Deduplication** - One price per (symbol, timestamp) regardless of data source
- **Extended Hours Tracking** - is_extended field to distinguish regular vs pre/post-market hours
- **Volume Strategy** - Plain integers for stocks (whole shares), micros only for fractional crypto volumes
- **Structured Analysis** - Rich JSON format with actual prices, targets, and detailed reasoning
- **Quick Stance Filter** - Bullish/neutral/bearish classification for rapid signal filtering
- **Break-Even Tracking** - Portfolio cost basis with trading fees factored into break-even price

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