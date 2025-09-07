# Summary.md - Codebase Index for LLMs

## Guide to Updating Summary.md

When updating this file, follow this checklist:
1. **Directory changes**: If new directories are added, document their purpose
2. **File changes**: When files are added/removed, update the file lists under each module
3. **Function/Class changes**: When functions or classes are added/modified/removed, update their entries
4. **Enum changes**: Always document enums with their values as they're database-critical
5. **Keep descriptions brief**: One-line purpose descriptions, focus on WHAT not HOW
6. **Alphabetical order**: Keep functions/classes in alphabetical order within each file section
7. **Include all public APIs**: Document all functions/classes that other modules import
8. **Test updates**: When test structure changes, update the tests/ section

---

## Core Idea
Framework for US equities data collection and LLM-ready storage. Current scope: strict UTC models, SQLite with constraints/dedup, and LLM provider integrations (OpenAI, Gemini). Automated polling/scheduling and trading decisions are not implemented yet; session support exists but no ET conversion or trading engine is present.

## Time Policy
- Persistence: UTC everywhere (ISO `YYYY-MM-DDTHH:MM:SSZ`).
- Sessions: `Session = {REG, PRE, POST}` is available in models. ET conversion helpers and session-detection logic are not implemented yet; providers currently normalize datetimes to UTC and, where needed, default `session` (e.g., Finnhub quotes use `Session.REG`).

## Environment Variables
- `FINNHUB_API_KEY` - Required for market data fetching
- `OPENAI_API_KEY` - Required for OpenAI LLM provider
- `GEMINI_API_KEY` - Required for Gemini LLM provider
- `DATABASE_PATH` - Optional, defaults to data/trading_bot.db

## Test Markers
- `@pytest.mark.integration` - Integration tests requiring database/API setup
- `@pytest.mark.network` - Tests requiring network connectivity

## Project Structure

### `config/` — Typed settings and retry configuration
**Purpose**: Provider settings, environment loaders, and retry policies

**Files**:
- `config/__init__.py` - Package marker
- `config/retry.py` - Retry configuration dataclasses and defaults
  - `LLMRetryConfig` - Configuration for LLM providers (timeout=360s, max_retries=3)
  - `DataRetryConfig` - Configuration for data providers (timeout=30s, max_retries=3)
  - `DEFAULT_LLM_RETRY` - Default LLMRetryConfig instance
  - `DEFAULT_DATA_RETRY` - Default DataRetryConfig instance

**Subdirectories**:
- `config/llm/` - LLM provider settings
  - `config/llm/__init__.py` - Package marker
  - `config/llm/gemini.py`
    - `GeminiSettings` - Dataclass for Gemini configuration
    - `GeminiSettings.from_env()` - Load settings from environment
  - `config/llm/openai.py`
    - `OpenAISettings` - Dataclass for OpenAI configuration
    - `OpenAISettings.from_env()` - Load settings from environment

- `config/providers/` - Data provider settings
  - `config/providers/finnhub.py`
    - `FinnhubSettings` - Dataclass for Finnhub configuration
    - `FinnhubSettings.from_env()` - Load settings from environment

### `data/` — Data models, storage, and providers
**Purpose**: Core data structures, SQLite operations, and data source implementations

**Files**:
- `data/__init__.py` - Package marker
- `data/schema.sql` - SQLite schema definition with constraints

- `data/base.py` - Abstract base classes for data sources
  - `DataSource` - Base class for all data sources
  - `DataSourceError` - Exception for data source failures
  - `NewsDataSource` - Abstract class for news providers
  - `PriceDataSource` - Abstract class for price providers

- `data/models.py` - Core dataclasses and enums
  **Enums**:
  - `Session` - Trading sessions: REG="REG", PRE="PRE", POST="POST"
  - `Stance` - Analysis stances: BULLISH="BULLISH", BEARISH="BEARISH", NEUTRAL="NEUTRAL"
  - `AnalysisType` - Analysis types: TECHNICAL="TECHNICAL", FUNDAMENTAL="FUNDAMENTAL", SENTIMENT="SENTIMENT"
  
  **Dataclasses**:
  - `NewsItem` - News article with url, headline, summary, symbols, source, published_at
  - `PriceData` - Price snapshot with symbol, price, volume, timestamp, session
  - `AnalysisResult` - LLM analysis with symbol, analysis_type, stance, confidence, reasoning, metadata, analyzed_at
  - `Holdings` - Portfolio holdings with symbol, shares, avg_price, total_value, last_updated, metadata
  
  **Functions**:
  - `_valid_http_url()` - Validate HTTP/HTTPS URLs

- `data/storage.py` - SQLite storage operations
  **Database Management**:
  - `init_database()` - Create tables and enable WAL mode
  - `finalize_database()` - Checkpoint WAL and optimize database
  
  **Storage Operations**:
  - `store_news_items()` - Insert news with deduplication by URL
  - `store_price_data()` - Insert price data
  - `upsert_analysis_result()` - Insert/update analysis results
  - `upsert_holdings()` - Insert/update holdings
  
  **Query Operations**:
  - `get_news_since()` - Fetch news after timestamp
  - `get_price_data_since()` - Fetch prices after timestamp
  - `get_all_holdings()` - Fetch all current holdings
  - `get_analysis_results()` - Fetch analysis results (optional symbol filter)
  - `get_news_before()` - Fetch news before cutoff (for LLM batching)
  - `get_prices_before()` - Fetch prices before cutoff (for LLM batching)
  
  **Watermark Management**:
  - `get_last_seen()` - Get last processed timestamp for a key
  - `set_last_seen()` - Update last processed timestamp
  - `get_last_news_time()` - Get last news timestamp
  - `set_last_news_time()` - Update last news timestamp
  
  **LLM Batch Operations**:
  - `commit_llm_batch()` - Mark data as processed and return counts
  
  **Internal Helpers**:
  - `_normalize_url()` - Standardize URLs for deduplication
  - `_datetime_to_iso()` - Convert datetime to ISO string
  - `_decimal_to_text()` - Convert Decimal to string
  - `_check_json1_support()` - Verify SQLite JSON1 extension
  - `_row_to_news_item()` - Convert DB row to NewsItem
  - `_row_to_price_data()` - Convert DB row to PriceData
  - `_row_to_analysis_result()` - Convert DB row to AnalysisResult
  - `_row_to_holdings()` - Convert DB row to Holdings

**Subdirectories**:
- `data/providers/` - Data source implementations
  - `data/providers/finnhub.py`
    - `FinnhubClient` - HTTP client for Finnhub API with retry logic
      - `__init__()` - Initialize with settings
      - `get()` - Make authenticated API request with retry
    - `FinnhubNewsProvider` - News fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Test API connectivity
      - `fetch_incremental()` - Fetch news since timestamp
      - `_parse_article()` - Convert API response to NewsItem
    - `FinnhubPriceProvider` - Price quote fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Test API connectivity
      - `fetch_incremental()` - Fetch current prices
      - `_parse_quote()` - Convert API response to PriceData

### `llm/` — LLM provider abstractions
**Purpose**: Base classes and provider implementations for LLM interactions

**Files**:
- `llm/__init__.py` - Package marker

- `llm/base.py` - Abstract base classes
  - `LLMProvider` - Base class for all LLM providers
    - `__init__()` - Store provider configuration
    - `generate()` - Abstract method for text generation
    - `validate_connection()` - Abstract method for connectivity test
  - `LLMError` - Exception for LLM failures

**Subdirectories**:
- `llm/providers/` - LLM provider implementations
  - `llm/providers/openai.py`
    - `OpenAIProvider` - OpenAI implementation using Responses API
      - `__init__()` - Configure with model, temperature, tools, tool_choice, reasoning
      - `generate()` - Send prompt and get response
      - `validate_connection()` - Test API connectivity
      - `_classify_openai_exception()` - Map SDK errors to retry logic
  
  - `llm/providers/gemini.py`
    - `GeminiProvider` - Google Gemini implementation
      - `__init__()` - Configure with model, temperature, tools, thinking_config
      - `generate()` - Send prompt and get response
      - `validate_connection()` - Test API connectivity
      - `_classify_gemini_exception()` - Map SDK errors to retry logic

### `utils/` — Shared utilities
**Purpose**: Cross-cutting concerns like retry logic and HTTP helpers

**Files**:
- `utils/__init__.py` - Package marker

- `utils/retry.py` - Retry logic with exponential backoff
  - `RetryableError` - Exception with retry_after hint
  - `parse_retry_after()` - Parse Retry-After header values
  - `retry_and_call()` - Generic async retry wrapper with backoff

- `utils/http.py` - HTTP utilities
  - `get_json_with_retry()` - Fetch JSON with automatic retry on failures

### `tests/` — Test suite
**Purpose**: Unit and integration tests with fixtures

**Structure**:
- `tests/conftest.py` - Shared pytest fixtures
  - `temp_db_path` - Temporary database path with cleanup
  - `temp_db` - Initialized temporary database
  - `mock_http_client` - Mock httpx client for testing
  - `cleanup_sqlite_artifacts()` - Windows-safe SQLite cleanup

- `tests/unit/` - Unit tests (mirror source structure)
  - `tests/unit/config/` - Config module tests
    - `test_config_retry.py` - Retry configuration tests
    - `llm/test_gemini.py` - Gemini settings tests
    - `llm/test_openai.py` - OpenAI settings tests
    - `providers/test_finnhub_settings.py` - Finnhub settings tests
  
  - `tests/unit/data/` - Data module tests
    - `test_base_contracts.py` - Abstract base class tests
    - `test_models.py` - Dataclass validation tests
    - `test_schema_*.py` - Database constraint tests (6 files)
    - `test_storage_*.py` - Storage function tests (12 files, split by feature)
    - `providers/test_finnhub.py` - Finnhub provider unit tests
    - `providers/test_finnhub_critical.py` - Critical error handling tests
  
  - `tests/unit/utils/` - Utils module tests
    - `test_http.py` - HTTP utility tests
    - `test_utils_retry.py` - Retry logic tests

- `tests/integration/` - Integration tests (organized by workflow)
  - `tests/integration/data/` - Data integration tests
    - `test_roundtrip_e2e.py` - Full data pipeline test
    - `test_dedup_news.py` - News deduplication test
    - `test_timezone_pipeline.py` - UTC conversion test
    - `test_decimal_precision.py` - Decimal handling test
    - `test_schema_constraints.py` - Database constraints test
    - `test_wal_sqlite.py` - WAL mode test
    - `providers/test_finnhub_live.py` - Live API test (network-marked)
  
  - `tests/integration/llm/` - LLM integration tests
    - `test_providers.py` - Live LLM provider tests (network-marked)
      - Tests SHA-256 tool use for both OpenAI and Gemini

## Database Schema
Tables (WITHOUT ROWID):
- `news_items(symbol, url, headline, summary, source, published_at, created_at)` - PK: (symbol, url)
- `price_data(symbol, price, volume, timestamp, session, created_at)` - PK: (symbol, timestamp)
- `analysis_results(symbol, analysis_type, stance, confidence, reasoning, metadata, analyzed_at, created_at)` - PK: (symbol, analysis_type)
- `holdings(symbol, shares, avg_price, total_value, last_updated, metadata, created_at)` - PK: symbol
- `last_seen(key, value)` - Watermarks for incremental processing

Constraints: NOT NULL on required fields, CHECK constraints for positive values, enum validations, JSON object validation for metadata fields