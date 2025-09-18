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
Framework for US equities data collection and LLM-ready storage. Current scope: strict UTC models, SQLite with constraints/dedup, LLM provider integrations (OpenAI, Gemini), and a configurable (5 mins for now) Finnhub poller. Trading decisions are not implemented yet; session detection is implemented via ET conversion.

## Time Policy
- Persistence: UTC everywhere (ISO `YYYY-MM-DDTHH:MM:SSZ`).
- Sessions: `Session = {REG, PRE, POST, CLOSED}` is available in models. ET conversion and session classification are implemented; providers normalize timestamps to UTC and use `utils.market_sessions.classify_us_session()` to set the session.

## Environment Variables
- `FINNHUB_API_KEY` - Required for market data fetching
- `OPENAI_API_KEY` - Required for OpenAI LLM provider
- `GEMINI_API_KEY` - Required for Gemini LLM provider
- `DATABASE_PATH` - Optional, defaults to data/trading_bot.db
- `SYMBOLS` - Required for `run_poller.py`; comma-separated tickers (e.g., "AAPL,MSFT,TSLA")
- `POLL_INTERVAL` - Required for `run_poller.py`; polling frequency in seconds (e.g., 300 for 5 minutes)
- `DATASETTE_PORT` - Optional, defaults to 8001; port used when launching web viewer with `-v/--with-viewer`

## Test Markers
- `@pytest.mark.integration` - Integration tests requiring database/API setup
- `@pytest.mark.network` - Tests requiring network connectivity

## Main Entry Points
- `run_poller.py` - Main data collection script
  - `main()` - Async entry point with signal handling
  - Uses `utils.logging.setup_logging()` for consistent logging
  - Uses `utils.signals.register_graceful_shutdown()` for SIGINT/SIGTERM
  - Requires `SYMBOLS`, `POLL_INTERVAL`, and `FINNHUB_API_KEY` in environment
  - Optional web viewer: run with `-v/--with-viewer` (port configurable via `DATASETTE_PORT`, default 8001)

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
  - `Session` - Trading sessions: REG, PRE, POST, CLOSED
  - `Stance` - Analysis stances: BULL, BEAR, NEUTRAL
  - `AnalysisType` - Types: `news_analysis`, `sentiment_analysis`, `sec_filings`, `head_trader`
  
  **Dataclasses**:
  - `NewsItem` - `symbol`, `url`, `headline`, `published` (UTC), `source`, `content` (optional)
  - `PriceData` - `symbol`, `timestamp` (UTC), `price` (Decimal), `volume` (optional), `session` (Session)
  - `AnalysisResult` - `symbol`, `analysis_type` (AnalysisType), `model_name`, `stance` (Stance), `confidence_score` (0–1), `last_updated` (UTC), `result_json` (JSON string), `created_at` (UTC, optional)
  - `Holdings` - `symbol`, `quantity` (Decimal), `break_even_price` (Decimal), `total_cost` (Decimal), `notes` (optional), `created_at`/`updated_at` (UTC, optional)
  
  **Functions**:
  - `_valid_http_url()` - Validate HTTP/HTTPS URLs

- `data/poller.py` - Data poller orchestration
  - `DataPoller` — Orchestrates multiple providers concurrently
    - `__init__(db_path, news_providers: list[NewsDataSource], price_providers: list[PriceDataSource], poll_interval: int)`
    - `poll_once()` — Fetches news/prices; updates watermark to latest news publish time
    - `run()` — Configurable interval loop with consistent-interval scheduling and graceful stop
    - `stop()` — Requests shutdown

- `data/storage.py` - SQLite storage operations
  **Database Management**:
  - `init_database()` - Create tables (WAL via schema PRAGMA)
  - `finalize_database()` - Checkpoint WAL and optimize database
  
  **Storage Operations**:
  - `store_news_items()` - Insert news with URL normalization + dedup
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
  - `get_last_seen()` - Get last processed value for a key
  - `set_last_seen()` - Update last processed value
  - `get_last_news_time()` - Get last news publish timestamp
  - `set_last_news_time()` - Update last news publish timestamp
  
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

- `data/poller.py` - Data collection orchestration
  - `DataPoller` - Manages configurable polling cycles
    - `__init__()` - Initialize with database path, lists of providers, and poll_interval
    - `poll_once()` - Execute single polling cycle for all providers concurrently
    - `run()` - Continuous polling loop with interval management
    - `stop()` - Graceful shutdown

**Subdirectories**:
- `data/providers/` - Data source implementations
- `data/providers/finnhub.py`
    - `FinnhubClient` - HTTP client for Finnhub API with retry logic
      - `__init__()` - Initialize with settings
      - `get()` - Make authenticated API request with retry
      - `validate_connection()` - Centralized API validation used by providers
    - `FinnhubNewsProvider` - News fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental()` - Fetch news since timestamp
      - `_parse_article()` - Convert API response to NewsItem
    - `FinnhubPriceProvider` - Price quote fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental()` - Fetch current prices
      - `_parse_quote()` - Convert API response to PriceData with ET-based session detection

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
        - Defaults: if `reasoning` is not provided, the provider sets `{"effort": "low"}` (keeps tool compatibility and reduces cost vs. higher efforts)
        - Note: `code_interpreter` cannot be used with `reasoning.effort = "minimal"` (API rejects that combo)
      - `generate()` - Send prompt and get response
      - `validate_connection()` - Test API connectivity
      - `_classify_openai_exception()` - Map SDK errors to retry logic
  
  - `llm/providers/gemini.py`
    - `GeminiProvider` - Google Gemini implementation
      - `__init__()` - Configure with model, temperature, tools, thinking_config
        - Defaults: if `thinking_config` is not provided, the provider sets `{"thinking_budget": 128}` (small but non‑zero reasoning budget)
        - Code execution is opt‑in via `tools=[{"code_execution": {}}]`
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
  - `get_json_with_retry(url, *, params=None, headers=None, timeout, max_retries, base=..., mult=..., jitter=...)` - Async GET JSON with retries; supports query params and custom headers (e.g., User‑Agent)
  
- `utils/logging.py` - Centralized logging configuration
  - `setup_logging()` - Configure logging level/format/handlers from env

- `utils/signals.py` - Graceful shutdown utilities
  - `register_graceful_shutdown(on_stop)` - Cross‑platform SIGINT/SIGTERM registration

- `utils/market_sessions.py` - US equity market session classification with NYSE calendar integration
  - `classify_us_session(ts_utc)` - Determine if timestamp is PRE/REG/POST/CLOSED based on ET trading hours and NYSE calendar (holidays, early closes)

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
    - `schema/` - Database constraint tests (6 files)
      - `test_schema_*.py` - Schema validation tests organized by constraint type
    - `storage/` - Storage function tests (12 files)
      - `test_storage_*.py` - Storage operations tests organized by feature
    - `test_poller.py` - DataPoller orchestrator tests (one-cycle store, watermark, errors)
    - `providers/test_finnhub.py` - Finnhub provider unit tests
    - `providers/test_finnhub_critical.py` - Critical error handling tests
  
  - `tests/unit/utils/` - Utils module tests
    - `test_http.py` - HTTP utility tests
    - `test_market_sessions.py` - Market sessions classification tests with holiday/early close support
    - `test_retry.py` - Retry logic tests

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
    - `helpers.py` - Shared helpers: `extract_hex64`, `fetch_featured_wiki`, `make_base64_blob`, `normalize_title`
    - `test_openai_provider.py` - OpenAI live tests (network-marked)
      - Web search check: with `tools=[{"type":"web_search"}]` and `tool_choice="auto"` → returns yesterday’s Wikipedia Featured article title; without tools (`tool_choice="none"`) → response should not contain the correct title
    - `test_gemini_provider.py` - Gemini live tests (network-marked)
      - Web search check: with `tools=[{"google_search":{}}]` → returns yesterday’s Wikipedia Featured article title; without tools → response should not contain the correct title
    - Notes: Requires API keys; uses Wikipedia with a descriptive `User-Agent`; network issues may fail tests

## Database Schema
Tables (WITHOUT ROWID):
- `news_items(symbol, url, headline, content, published_iso, source, created_at_iso)` — PK: (symbol, url)
- `price_data(symbol, timestamp_iso, price TEXT, volume, session, created_at_iso)` — PK: (symbol, timestamp_iso)
- `analysis_results(symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json, created_at_iso)` — PK: (symbol, analysis_type)
- `holdings(symbol, quantity TEXT, break_even_price TEXT, total_cost TEXT, notes, created_at_iso, updated_at_iso)` — PK: symbol
- `last_seen(key, value)` — Watermarks (`news_since_iso`, `llm_last_run_iso`)

Constraints: NOT NULL on required fields, CHECK constraints for positive values, enum validations, JSON object validation for JSON columns
