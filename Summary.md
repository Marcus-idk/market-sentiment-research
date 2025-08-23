# TradingBot Codebase Summary

## Current Implementation Status
- **✅ v0.1 COMPLETED**: LLM Provider Module (OpenAI, Gemini with full async support)
- **✅ v0.2 Phase 1 COMPLETED**: Core Data Infrastructure (models, storage, database schema)
- **✅ v0.2 Phase 1 Testing COMPLETED**: Data Model Validation Test Suite (comprehensive __post_init__ validation)
- **✅ v0.2 Phase 2 Testing COMPLETED**: Storage Operations Test Suite (CRUD, Windows-safe SQLite cleanup)
- **✅ v0.2 Phase 3 Testing COMPLETED**: Database Schema Constraint Test Suite (direct SQL constraint validation)
- **🔄 v0.2+ PLANNED**: API Data Providers (Finnhub, RSS, Reddit, SEC EDGAR, Polygon)

## Technical Stack
- **Python** - Core language for financial libraries and LLM integrations
- **Async/Await** - For concurrent API calls to multiple data sources (LLM providers implemented)
- **SQLite Database** - Local storage with optimized schema and WAL mode
- **Dataclasses** - Type-safe models with validation for financial data

## Market Focus & Timezone Strategy
- **Target Market**: US Stock Market (NYSE, NASDAQ) exclusively
- **Trading Sessions**: 
  - Pre-market: 4:00 AM - 9:30 AM ET
  - Regular: 9:30 AM - 4:00 PM ET
  - Post-market: 4:00 PM - 8:00 PM ET
- **Timezone Handling**: All timestamps stored in UTC (Z suffix) for consistency
  - Database storage: ISO format with UTC (e.g., `2024-01-01T14:30:00Z`)
  - Internal processing: Convert to ET for trading logic
  - Session enum: `REG`, `PRE`, `POST` correspond to US market sessions
- **Supported Securities**: US-listed stocks only (no crypto, forex, or international markets in v0.2)

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
- `validate_connection()` - Test if provider is properly configured (async)

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
Purpose: Comprehensive validation of LLM provider functionality and data infrastructure for automated trading system.

#### tests/conftest.py
Purpose: Shared pytest fixtures and utilities for all tests.
- `cleanup_sqlite_artifacts()` - Windows-safe SQLite cleanup for WAL databases (solves file locking issues)
- Automatically discovered by pytest and available to all test files

#### tests/test_llm_providers.py
Purpose: Basic connectivity and functionality testing for production readiness.

Features:
- Connection validation tests for both OpenAI and Gemini providers
- SHA-256 hash tool validation to verify code execution functionality
- Environment variable validation
- Graceful skipping when API keys are unavailable
- Direct execution support for development workflow

#### tests/test_data_models.py
Purpose: Phase 1 data model validation tests - comprehensive __post_init__ validation.
- `TestNewsItem` - URL validation (http/https only), empty field validation, timezone normalization
- `TestPriceData` - Price positivity (> 0), volume validation (≥ 0), Session enum validation, Decimal precision, timezone normalization, symbol validation
- `TestAnalysisResult` - JSON object validation, confidence range (0.0-1.0), AnalysisType/Stance enum validation, timezone normalization, symbol validation, empty string validation
- `TestHoldings` - Financial values positivity (quantity/price/cost > 0), Decimal precision preservation, timezone normalization, symbol validation, notes trimming

Key Features:
- **Pure Python Testing** - All `__post_init__` validation logic with no database dependencies
- **Critical Gaps Fixed** - Added missing timezone, symbol, and empty string validation tests
- **Comprehensive Coverage** - All enum validations, financial value constraints, JSON validation, timezone handling
- **Pytest Integration** - Uses pytest framework with clear test organization and error matching

#### tests/test_data_storage.py
Purpose: Phase 2 storage operations testing - comprehensive SQLite CRUD operations with Windows-safe cleanup.
- **Windows-Safe SQLite Cleanup** - Solves Windows file locking with WAL checkpoint and journal mode switching
- **Storage CRUD Operations** - Tests for all storage functions with type conversions
- **URL Normalization** - Validates tracking parameter stripping for deduplication
- **Decimal/DateTime Conversions** - Tests TEXT storage precision and ISO timestamp formatting
- **Database Initialization** - Validates schema loading and constraint setup

Key Features:
- **856 Lines of Tests** - Comprehensive coverage of all storage operations
- **Windows Compatibility** - Uses mkstemp() + cleanup_sqlite_artifacts() pattern
- **WAL Mode Testing** - Production parity with Write-Ahead Logging mode
- **Type Safety** - Validates all Decimal↔TEXT and datetime↔ISO conversions

#### tests/test_data_schema.py
Purpose: Phase 3 database schema constraint testing - direct SQL validation bypassing Python models.
- `TestNotNullConstraints` - Validates NOT NULL constraints across all 24 required fields
- `TestFinancialConstraints` - Tests positive value constraints (price, quantity, costs > 0)
- `TestPrimaryKeyConstraints` - Tests duplicate key violations for all 4 tables
- `TestVolumeConstraints` - Tests volume >= 0 with NULL handling
- `TestEnumConstraints` - Tests session, stance, analysis_type valid/invalid values (fixed UTC timestamps)
- `TestConfidenceScoreRange` - Tests BETWEEN 0 AND 1 constraint with boundaries
- `TestJSONConstraints` - Tests json_valid() and json_type()='object' (conditional on JSON1)
- `TestDefaultValues` - Tests session='REG' and timestamp defaults
- `TestTableStructure` - Validates WITHOUT ROWID optimization

Key Features:
- **Direct SQL Testing** - Bypasses Python validation to test database constraints
- **JSON1 Detection** - Conditional testing based on SQLite extension availability
- **Windows-Safe Pattern** - Uses shared cleanup_sqlite_artifacts() from conftest.py
- **Comprehensive Coverage** - ~30 tests covering all CHECK, NOT NULL, and PRIMARY KEY constraints
- **Boundary Testing** - Explicit edge cases (0.000001, 999999999.99, etc.)
- **Fixed Session Timestamps** - Proper UTC hour mapping for REG/PRE/POST sessions

**Planned Test Files (🔄 v0.2 Phases 4-5)**:
- `test_data_base_classes.py` - Phase 4: Base class validation, DataSource abstract method enforcement
- `test_data_integration.py` - Phase 5: Integration tests, end-to-end workflows

### data/ - Data Collection Module

#### __init__.py
Purpose: Clean exports for data collection components.

Exports:
- `DataSource` - Abstract base class for all data providers
- `NewsDataSource` - Abstract base class for news content providers  
- `PriceDataSource` - Abstract base class for price/market data providers
- `NewsItem` - Data model for news articles
- `PriceData` - Data model for financial price/market data
- `AnalysisResult` - Data model for LLM analysis results
- `Holdings` - Data model for portfolio positions
- `Session` - Enum for trading session types (REG, PRE, POST)
- `Stance` - Enum for analysis stance types (BULL, BEAR, NEUTRAL)
- `AnalysisType` - Enum for LLM analysis types (NEWS_ANALYSIS, SENTIMENT_ANALYSIS, SEC_FILINGS, HEAD_TRADER)
- `init_database` - Initialize SQLite database from schema
- `store_news_items` - Store news items with deduplication
- `store_price_data` - Store price data with type conversion
- `get_news_since` - Query news items since timestamp
- `get_price_data_since` - Query price data since timestamp
- `upsert_analysis_result` - Insert/update analysis results
- `upsert_holdings` - Insert/update portfolio holdings
- `get_all_holdings` - Query all current holdings
- `get_analysis_results` - Query analysis results by symbol

#### base.py
Purpose: Abstract base class defining the contract for all data source providers.

Classes:
- `DataSource` - Abstract base class with shared functionality and input validation
- `NewsDataSource` - Abstract base class for news providers (inherits from DataSource)
  - `fetch_incremental(since)` - Fetch new news items since timestamp (async, returns List[NewsItem])
- `PriceDataSource` - Abstract base class for price data providers (inherits from DataSource)
  - `fetch_incremental(since)` - Fetch new price data since timestamp (async, returns List[PriceData])
- `DataSourceError` - Base exception for data source related errors
- `RateLimitError` - Exception for API rate limit exceeded scenarios

Functions:
- `validate_connection()` - Test if data source is reachable (async, returns bool)
- `update_last_fetch_time(timestamp)` - Update last successful fetch timestamp
- `get_last_fetch_time()` - Get last successful fetch timestamp

Input Validation:
- Constructor validates source_name (non-empty string, max 100 chars)
- update_last_fetch_time validates timestamp (not None, not future, proper type)
- Comprehensive error messages for debugging

#### models.py
Purpose: Complete Data Transfer Objects (DTOs) for v0.2 core functionality with LLM analysis and portfolio tracking.

Enums:
- `Session` - Trading session types (REG, PRE, POST)
- `Stance` - Analysis stance types (BULL, BEAR, NEUTRAL)
- `AnalysisType` - LLM analysis types (NEWS_ANALYSIS, SENTIMENT_ANALYSIS, SEC_FILINGS, HEAD_TRADER)

Classes:
- `NewsItem` - Data model for news articles from various sources
  - Required fields: symbol, url, headline, published (datetime), source
  - Optional fields: content
  - Input validation in __post_init__ (non-empty strings, valid HTTP URLs, timezone handling)
- `PriceData` - Data model for financial price/market data from various sources
  - Required fields: symbol, timestamp (datetime), price (Decimal)
  - Optional fields: volume, session (Session enum for REG/PRE/POST market hours)
  - Input validation in __post_init__ (non-empty symbol, price must be > 0, volume ≥ 0, timezone handling)
- `AnalysisResult` - Data model for LLM analysis results
  - Required fields: symbol, analysis_type (AnalysisType enum), model_name, stance (Stance enum), confidence_score (0.0-1.0), last_updated (datetime), result_json
  - Optional fields: created_at (datetime)
  - Input validation in __post_init__ (non-empty strings, enum validation, confidence range validation, timezone handling)
- `Holdings` - Data model for portfolio positions
  - Required fields: symbol, quantity (Decimal), break_even_price (Decimal), total_cost (Decimal)
  - Optional fields: notes, created_at (datetime), updated_at (datetime)
  - Input validation in __post_init__ (non-empty symbol, positive financial values, timezone handling)

Features:
- Complete model set for v0.2 requirements (storage + LLM analysis + portfolio tracking)
- Robust input validation with automatic string trimming and timezone normalization
- URL validation for news items and JSON syntax validation for analysis results
- Uses @dataclass for clean field definitions and automatic methods
- Decimal precision for financial data stored as TEXT strings to prevent floating-point errors
- Enum validation for structured data consistency
- Positive value validation (price, quantity, costs must be > 0, not just >= 0)

#### storage.py
Purpose: SQLite storage operations providing CRUD functionality for all trading bot data models.

Functions:
- `init_database(db_path)` - Initialize database by executing schema.sql with performance optimizations
- `store_news_items(db_path, items)` - Store news with URL normalization and duplicate handling
- `store_price_data(db_path, items)` - Store price data with Decimal-to-TEXT conversion
- `get_news_since(db_path, timestamp)` - Retrieve news items since timestamp (returns raw dicts)
- `get_price_data_since(db_path, timestamp)` - Retrieve price data since timestamp (returns raw dicts)
- `upsert_analysis_result(db_path, result)` - Insert/update LLM analysis results with conflict resolution
- `upsert_holdings(db_path, holdings)` - Insert/update portfolio positions with conflict resolution
- `get_all_holdings(db_path)` - Retrieve all current holdings (returns raw dicts)
- `get_analysis_results(db_path, symbol=None)` - Retrieve analysis results, optionally filtered by symbol

Key Features:
- **URL Normalization** - `_normalize_url()` strips tracking parameters for cross-provider deduplication
- **Type Conversions** - `_datetime_to_iso()` and `_decimal_to_text()` for database storage format
- **INSERT OR IGNORE** - Graceful duplicate handling for raw data storage
- **ON CONFLICT** - Upsert operations for analysis results and holdings updates
- **Raw Dict Returns** - Query functions return raw dictionaries for flexible processing
- **Transaction Safety** - All operations use context managers for automatic commit/rollback

#### schema.sql
Purpose: SQLite database schema with expert performance optimizations.

Database Architecture:
- **Raw Data Tables** - Temporary storage for news and price data
- **Analysis Results Tables** - Persistent storage for LLM analysis results and portfolio holdings

Tables:
- `news_items` - Temporary storage for news articles (PRIMARY KEY: symbol, url)
- `price_data` - Temporary storage for financial price data (PRIMARY KEY: symbol, timestamp_iso)
- `analysis_results` - Persistent LLM analysis results per (symbol, analysis_type) with structured reasoning
- `holdings` - Portfolio tracking with break-even calculations (PRIMARY KEY: symbol)

Expert Optimizations:
- **WAL Mode** - Allows concurrent reads during writes (prevents database locks)
- **WITHOUT ROWID** - Performance optimization for natural primary keys
- **ISO Timestamps Only** - Human-readable ISO format (YYYY-MM-DDTHH:MM:SSZ) for easier querying and debugging
- **URL Normalization** - Strip tracking parameters for cross-provider deduplication
- **TEXT Decimal Storage** - Store financial values as TEXT strings for exact precision (no floating-point errors)
- **Database CHECK Constraints** - Validate decimal TEXT fields can be cast to positive REAL values
- **Price Deduplication** - One price per (symbol, timestamp_iso) regardless of data source
- **Session Tracking** - session field with enum values (REG/PRE/POST) to distinguish trading sessions
- **Volume Strategy** - INTEGER storage for whole shares only (fractional volumes not supported in v0.2)
- **Structured Analysis** - Rich JSON format with syntax validation and stance filtering
- **JSON Validation** - CHECK constraints and Python validation for properly formed JSON content
- **Positive Value Enforcement** - All financial values must be > 0 (price, quantity, costs)
- **Simplified Holdings** - Essential fields only (quantity, break-even, total cost) for v0.2 core functionality

#### providers/
Purpose: Directory for data API provider implementations.

**STATUS: 🔄 NOT IMPLEMENTED** - Directory exists but contains no provider implementations yet.

Planned implementations (v0.21+):
- Finnhub API providers (news + price data)
- RSS feed providers (news)  
- Reddit PRAW providers (sentiment)
- SEC EDGAR providers (regulatory filings)
- Polygon.io providers (market data backup)

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