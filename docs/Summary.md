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
9. **Ignore tempFiles/**: Do not flag tempFiles/ directory for updates; it contains temporary planning notes only

---

## Core Idea
Framework for US equities data collection and LLM-ready storage. Current scope: strict UTC models, SQLite with constraints/dedup, LLM provider integrations (OpenAI, Gemini), and a configurable (5 mins for now) data poller with Finnhub and Polygon providers. Trading decisions are not implemented yet; session detection is implemented via ET conversion.

## Time Policy
- Persistence: UTC everywhere (ISO `YYYY-MM-DDTHH:MM:SSZ`).
- Sessions: `Session = {REG, PRE, POST, CLOSED}` is available in models. ET conversion and session classification are implemented; providers normalize timestamps to UTC and use `utils.market_sessions.classify_us_session()` to set the session.

## Environment Variables
- `FINNHUB_API_KEY` - Required for market data fetching
- `POLYGON_API_KEY` - Required for Polygon.io news data
- `OPENAI_API_KEY` - Required for OpenAI LLM provider
- `GEMINI_API_KEY` - Required for Gemini LLM provider
- `DATABASE_PATH` - Optional, defaults to data/trading_bot.db
- `SYMBOLS` - Required for `run_poller.py`; comma-separated tickers (e.g., "AAPL,MSFT,TSLA")
- `POLL_INTERVAL` - Required for `run_poller.py`; polling frequency in seconds (e.g., 300 for 5 minutes)
- `STREAMLIT_PORT` - Optional, defaults to 8501; port used when launching web UI with `-v`

## Test Markers
- `@pytest.mark.integration` - Integration tests requiring database/API setup
- `@pytest.mark.network` - Tests requiring network connectivity

## Top-Level Files
- `README.md` - Landing page that points developers to detailed documentation in `docs/`
- `requirements.txt` - Runtime and test dependencies (OpenAI, Gemini, httpx, pytest, etc.)
- `requirements-dev.txt` - Developer-only extras
- `pytest.ini` - Pytest configuration (pythonpath, markers, default flags)
- `.env.example` - Example environment configuration (copy to `.env` and set API keys)

## Main Entry Points
- `run_poller.py` - Main data collection script
  - `PollerConfig` - Configuration dataclass (db_path, symbols, poll_interval, ui_port, finnhub_settings, polygon_settings)
  - `setup_environment()` - Load environment variables and configure logging
  - `build_config()` - Parse environment variables and build PollerConfig object
  - `initialize_database()` - Initialize database and return success status
  - `launch_ui_process()` - Launch Streamlit UI process if `-v` flag provided
  - `create_and_validate_providers()` - Create and validate news/price providers, returns provider lists
  - `cleanup_ui_process()` - Terminate UI process on shutdown
  - `main()` - Async entry point with signal handling
  - Uses `utils.logging.setup_logging()` for consistent logging
  - Uses `utils.signals.register_graceful_shutdown()` for SIGINT/SIGTERM
  - Requires `SYMBOLS`, `POLL_INTERVAL`, `FINNHUB_API_KEY`, and `POLYGON_API_KEY` in environment
  - Optional web UI: run with `-v` (port configurable via `STREAMLIT_PORT`, default 8501)
- `ui/app_min.py` - Streamlit database UI. Run with `streamlit run ui/app_min.py` (uses `DATABASE_PATH`).

## Project Structure

### `config/` — Typed settings and retry configuration
**Purpose**: Provider settings, environment loaders, and retry policies

**Files**:
- `config/__init__.py` - Public facade (re-exports llm, providers, retry modules)
- `config/retry.py` - Retry configuration dataclasses and defaults
  - `DataRetryConfig` - Configuration for data providers (timeout_seconds=30, max_retries=3, base=0.25, mult=2.0, jitter=0.1)
  - `DEFAULT_DATA_RETRY` - Default data retry instance used across providers
  - `DEFAULT_LLM_RETRY` - Default LLM retry instance used across providers
  - `LLMRetryConfig` - Configuration for LLM providers (timeout_seconds=360, max_retries=3, base=0.25, mult=2.0, jitter=0.1)

**Subdirectories**:
- `config/llm/` - LLM provider settings
  - `config/llm/__init__.py` - Re-exports `OpenAISettings`, `GeminiSettings`
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
  - `config/providers/polygon.py`
    - `PolygonSettings` - Dataclass for Polygon.io configuration
    - `PolygonSettings.from_env()` - Load settings from environment

### `data/` — Data models, storage, and providers
**Purpose**: Core data structures, SQLite operations, and data source implementations

**Files**:
- `data/__init__.py` - Public facade (exports base classes, models, and storage operations)
- `data/schema.sql` - SQLite schema definition with constraints

- `data/base.py` - Abstract base classes for data sources
  - `DataSource` - Base class for all data sources
  - `DataSourceError` - Exception for data source failures
  - `NewsDataSource` - Abstract class for news providers
    - `fetch_incremental(*, since: datetime | None = None, min_id: int | None = None)` — unified cursor interface
      - Date-based providers use `since` (ignore `min_id`)
      - ID-based providers use `min_id` (ignore `since`)
  - `PriceDataSource` - Abstract class for price providers
    - `fetch_incremental(since: datetime | None = None)` — price fetch (since unused for quotes)

- `data/models.py` - Core dataclasses and enums
  **Enums**:
  - `AnalysisType` - Types: `news_analysis`, `sentiment_analysis`, `sec_filings`, `head_trader`
  - `NewsLabelType` - News focus tags: Company, People, MarketWithMention
  - `Session` - Trading sessions: REG, PRE, POST, CLOSED
  - `Stance` - Analysis stances: BULL, BEAR, NEUTRAL
  - `Urgency` - News urgency levels: URGENT, NOT_URGENT

  **Dataclasses**:
  - `AnalysisResult` - `symbol`, `analysis_type` (AnalysisType), `model_name`, `stance` (Stance), `confidence_score` (0–1), `last_updated` (UTC), `result_json` (JSON string), `created_at` (UTC, optional)
  - `Holdings` - `symbol`, `quantity` (Decimal), `break_even_price` (Decimal), `total_cost` (Decimal), `notes` (optional), `created_at`/`updated_at` (UTC, optional)
  - `NewsItem` - `symbol`, `url`, `headline`, `published` (UTC), `source`, `content` (optional)
  - `NewsLabel` - `symbol`, `url`, `label` (NewsLabelType), `created_at` (UTC, optional)
  - `PriceData` - `symbol`, `timestamp` (UTC), `price` (Decimal), `volume` (optional), `session` (Session)

  **Functions**:
  - `_normalize_to_utc()` - Normalize naive/aware datetimes to UTC for model constructors
  - `_valid_http_url()` - Validate HTTP/HTTPS URLs

- `data/storage/` - SQLite storage package (organized into focused modules)
  **Import paths unchanged**: All functions accessible via `from data.storage import ...`

  **Package Structure**:
  - `db_context.py` - Internal cursor context manager (1 helper)
    - `_cursor_context(db_path, commit=True)` - Preferred way to run DB ops; auto-commit on success, rollback on error, and enables `sqlite3.Row` row factory for dict-like access. Use `commit=False` for pure reads.

  - `storage_core.py` - Database lifecycle and connections (4 functions)
    - `connect()` - Open SQLite connection with required PRAGMAs (enables foreign keys)
    - `finalize_database()` - Checkpoint WAL and optimize database
    - `init_database()` - Create tables (WAL via schema PRAGMA)
    - `_check_json1_support()` - Verify SQLite JSON1 extension

  - `storage_crud.py` - CRUD operations for all data types (10 functions)
    - **Store**: `store_news_items()`, `store_news_labels()`, `store_price_data()`
    - **Query**: `get_news_since()`, `get_news_labels()`, `get_price_data_since()`, `get_all_holdings()`, `get_analysis_results()`
    - **Upsert**: `upsert_analysis_result()`, `upsert_holdings()`

  - `storage_batch.py` - Batch operations and watermarks (9 functions)
    - **Batch queries**: `get_news_before()`, `get_prices_before()` (for LLM processing)
    - **Batch operations**: `commit_llm_batch()` - Set `llm_last_run_iso` and prune processed rows across news/news_labels/price_data
    - **Watermarks**: `get_last_seen()`, `set_last_seen()`, `get_last_news_time()`, `set_last_news_time()`, `get_last_macro_min_id()`, `set_last_macro_min_id()`

  - `storage_utils.py` - Utilities and type converters (10 functions)
    - **Helpers**: `_datetime_to_iso()`, `_decimal_to_text()`, `_iso_to_datetime()`, `_normalize_url()`, `_parse_rfc3339()`
    - **Row converters**: `_row_to_analysis_result()`, `_row_to_holdings()`, `_row_to_news_item()`, `_row_to_news_label()`, `_row_to_price_data()`

**Subdirectories**:
- `data/providers/` - Data source implementations
  - `data/providers/__init__.py` - Public facade; import via `from data.providers import finnhub, polygon`
  - `data/providers/finnhub/`
    - `FinnhubClient` - HTTP client for Finnhub API with retry logic
      - `__init__()` - Initialize with settings
      - `get()` - Make authenticated GET request with retry logic (path, optional params)
      - `validate_connection()` - Centralized API validation used by providers
    - `FinnhubNewsProvider` - Company news fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(since=..., min_id=None)` - Date-based; applies 2‑min buffer; ignores `min_id`
      - `_parse_article()` - Convert API response to NewsItem
    - `FinnhubMacroNewsProvider` - Market-wide macro news fetching implementation
      - `__init__()` - Initialize with settings and symbols (watchlist for filtering)
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(since=None, min_id=...)` - ID-based; uses Finnhub `minId`; ignores `since`; tracks `last_fetched_max_id`
      - `_parse_article()` - Convert API response to NewsItem list per watchlist symbol, defaulting to 'ALL' when none match
    - `_extract_symbols_from_related()` - Filter `related` field against watchlist; if nothing survives, fallback to ['ALL'] for market-wide coverage
      - `last_fetched_max_id` - Stores latest article ID for watermark updates
    - `FinnhubPriceProvider` - Price quote fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental()` - Fetch current prices (drops `since` kwarg from base class signature; quotes are real-time snapshots; minor LSP inconsistency but runtime-safe)
      - `_parse_quote()` - Convert API response to PriceData; skips missing/invalid/non-positive quotes; ET-based session detection
  - `data/providers/polygon/`
    - `PolygonClient` - HTTP client for Polygon.io API with retry logic
      - `__init__()` - Initialize with settings
      - `get()` - Make authenticated GET request with retry logic (path, optional params)
      - `validate_connection()` - API validation using market status endpoint
    - `PolygonNewsProvider` - Company news fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(since=...)` - Date-based; applies 2‑min buffer
      - `_fetch_symbol_news()` - Fetch news for single symbol with pagination until complete
      - `_extract_cursor()` - Extract cursor from Polygon next_url for pagination
      - `_parse_article()` - Convert API response to NewsItem; parses RFC3339 timestamps
    - `PolygonMacroNewsProvider` - Market-wide macro news fetching implementation
      - `__init__()` - Initialize with settings and symbols (watchlist for filtering)
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(since=...)` - Date-based; applies 2‑min buffer; handles pagination
      - `_extract_cursor()` - Extract cursor from Polygon next_url for pagination
      - `_parse_article()` - Convert API response to NewsItem list per watchlist symbol, defaulting to 'ALL' when none match
      - `_extract_symbols_from_tickers()` - Filter `tickers` array against watchlist; if nothing survives, fallback to ['ALL'] for market-wide coverage

### `llm/` — LLM provider abstractions
**Purpose**: Base classes and provider implementations for LLM interactions

**Files**:
- `llm/__init__.py` - Public facade (re-exports LLMProvider, OpenAIProvider, GeminiProvider)

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
  - `parse_retry_after()` - Parse Retry-After header values
  - `RetryableError` - Exception with retry_after hint
  - `retry_and_call()` - Generic async retry wrapper with backoff

- `utils/http.py` - HTTP utilities
  - `get_json_with_retry(url, *, params=None, headers=None, timeout, max_retries, base=..., mult=..., jitter=...)` - Async GET JSON with retries; supports query params and custom headers (e.g., User‑Agent)
  
- `utils/logging.py` - Centralized logging configuration
  - `setup_logging()` - Configure logging level/format/handlers from env

- `utils/signals.py` - Graceful shutdown utilities
  - `register_graceful_shutdown(on_stop)` - Cross-platform SIGINT/SIGTERM registration; returns unregister callback to restore handlers

- `utils/market_sessions.py` - US equity market session classification with NYSE calendar integration
  - `classify_us_session(ts_utc)` - Determine if timestamp is PRE/REG/POST/CLOSED based on ET trading hours and NYSE calendar (holidays, early closes)

- `utils/symbols.py` - Symbol parsing and validation helpers
  - `parse_symbols(raw, *, filter_to=None, validate=True, log_label="SYMBOLS")` - Parse comma-separated tickers, normalize to upper-case, optionally filter to a watchlist while deduplicating and validating format. Used by `run_poller.py` and Finnhub macro news provider.

### `workflows/` — Orchestration layer
**Purpose**: Coordinate data collection, processing, and analysis workflows

**Files**:
- `workflows/__init__.py` - Public facade (exports DataPoller)
- `workflows/poller.py` - Data collection orchestrator
  - `DataPoller` - Orchestrates multiple providers concurrently with news classification and urgency detection
    - `__init__(db_path, news_providers, price_providers, poll_interval)` - Initialize poller
    - `_fetch_all_data()` - Concurrently fetch news and prices; return company/macro news and per‑provider prices with errors
    - `_log_urgent_items()` - Log urgent news items to console
    - `_process_news()` - Store news, classify company items, detect urgency, update watermarks
    - `_process_prices()` - Deduplicate per symbol using primary provider; log mismatches ≥ $0.01; store primary only (framework complete; currently single provider: Finnhub)
    - `_read_watermarks()` - Read last_news_time and last_macro_min_id from database
    - `poll_once()` - One cycle: fetch, process, update watermarks, return stats
    - `run()` - Continuous polling loop with interval scheduling and graceful shutdown
    - `stop()` - Request graceful shutdown
  - `DataBatch` (TypedDict) - Batch result with `company_news`, `macro_news`, `prices: dict[str, dict[str, PriceData]]` (provider → {symbol → PriceData}), `errors`
  - `PollStats` (TypedDict) - Per-cycle stats with `news`, `prices`, `errors`

### `analysis/` — Business logic and classification
**Purpose**: News classification, sentiment analysis, and trading decisions

**Files**:
- `analysis/__init__.py` - Public facade (re-exports news_classifier, urgency_detector submodules)
- `analysis/news_classifier.py` - News classification module
  - `classify(news_items)` - Classify news into Company/People/MarketWithMention (currently stub returning 'Company' for all)
- `analysis/urgency_detector.py` - Urgency detection module
  - `detect_urgency(news_items)` - Detect urgent news requiring immediate attention (currently stub that logs cycle stats and returns empty list; LLM-based detection in v0.5)

### `ui/` — Web UI
**Purpose**: Lightweight Streamlit interface for local DB inspection

**Files**:
- `ui/app_min.py` - Default-style Streamlit app with:
  - "Table" select from `sqlite_master`
  - Reads `DATABASE_PATH` (defaults to `data/trading_bot.db`)

### `docs/` — Developer and operations documentation
**Files**:
- `docs/Data_API_Reference.md` - External data sources, rate limits, and implementation notes
- `docs/LLM_Providers_Guide.md` - LLM provider configuration cheat sheet (OpenAI, Gemini)
- `docs/Roadmap.md` - Milestones from v0.1 through v1.0 with status tracking
- `docs/Summary.md` - This code index, kept in sync with repository structure
- `docs/Test_Guide.md` - Testing structure, naming conventions, markers, and contract-testing rules
- `docs/Writing_Code.md` - Coding standards, design principles, and review checklist

### `tests/` — Test suite
**Purpose**: Unit and integration tests with shared fixtures

**Files**:
- `tests/__init__.py` - Package marker for pytest discovery
- `tests/conftest.py` - Shared pytest fixtures
  - `temp_db_path` - Temporary database path with cleanup
  - `temp_db` - Initialized temporary database
  - `mock_http_client` - Mock httpx client for HTTP tests
  - `cleanup_sqlite_artifacts()` - Windows-safe SQLite cleanup utility

**Subdirectories**:
- `tests/unit/` - Unit tests (mirror source structure)
  - `tests/unit/config/` - Configuration module tests
    - `tests/unit/config/contracts/test_settings_contract.py` - Shared `from_env` contract for Finnhub, Polygon, OpenAI, Gemini (API keys, defaults, error text)
    - `tests/unit/config/llm/test_gemini.py` - Reserved for Gemini-only settings behavior (core checks live in contracts)
    - `tests/unit/config/llm/test_openai.py` - Reserved for OpenAI-only settings behavior (core checks live in contracts)
    - `tests/unit/config/providers/test_finnhub_settings.py` - Reserved for Finnhub-only settings behavior (core checks live in contracts)
    - `tests/unit/config/providers/test_polygon_settings.py` - Reserved for Polygon-only settings behavior (core checks live in contracts)
    - `tests/unit/config/test_config_retry.py` - Retry configuration tests

  - `tests/unit/llm/` - LLM module tests
    - `tests/unit/llm/test_llm_base.py` - LLM provider base class contract tests

  - `tests/unit/data/` - Data module tests
    - `tests/unit/data/test_base_contracts.py` - Abstract base class contracts
    - `tests/unit/data/test_models.py` - Dataclass validation tests
  - `tests/unit/data/providers/` - Data provider tests
    - `tests/unit/data/providers/conftest.py` - Provider test fixtures (CompanyProviderSpec, MacroProviderSpec, PriceProviderSpec, ClientSpec)
    - `tests/unit/data/providers/contracts/` - Shared provider contract tests
      - `tests/unit/data/providers/contracts/test_client_contract.py` - Client behavior contracts (URL building, auth injection, validation)
      - `tests/unit/data/providers/contracts/test_news_company_contract.py` - Company news provider contracts (parsing, filtering, error isolation)
      - `tests/unit/data/providers/contracts/test_news_macro_contract.py` - Macro news provider contracts (symbol extraction, filtering, pagination)
      - `tests/unit/data/providers/contracts/test_prices_contract.py` - Price provider contracts (quote parsing, validation, session detection)
    - `tests/unit/data/providers/test_finnhub_client.py` - Finnhub-specific client tests (custom base URL; shared behaviors in contracts)
    - `tests/unit/data/providers/test_finnhub_news.py` - Finnhub company news tests (date window parameters; shared behaviors in contracts)
    - `tests/unit/data/providers/test_finnhub_macro.py` - Finnhub macro news tests (minId parameter, ID tracking; shared behaviors in contracts)
    - `tests/unit/data/providers/test_finnhub_prices.py` - Finnhub price tests (empty symbols handling; shared behaviors in contracts)
    - `tests/unit/data/schema/test_schema_confidence_and_json.py` - JSON fields and confidence constraints
    - `tests/unit/data/schema/test_schema_defaults_and_structure.py` - Default values and schema structure
    - `tests/unit/data/schema/test_schema_enums.py` - Enum value locking
    - `tests/unit/data/schema/test_schema_last_seen_keys.py` - Watermark key presence/constraints
    - `tests/unit/data/schema/test_schema_financial_values.py` - Decimal and numeric constraints
    - `tests/unit/data/schema/test_schema_not_null.py` - NOT NULL coverage
    - `tests/unit/data/schema/test_schema_primary_keys.py` - Primary key enforcement
    - `tests/unit/data/storage/test_storage_analysis.py` - Analysis result storage
    - `tests/unit/data/storage/test_storage_cutoff.py` - Time-based cutoff handling
    - `tests/unit/data/storage/test_storage_db.py` - Low-level database helpers
    - `tests/unit/data/storage/test_storage_db_context.py` - Database context manager tests
    - `tests/unit/data/storage/test_storage_errors.py` - Error pathways
    - `tests/unit/data/storage/test_storage_holdings.py` - Holdings persistence
    - `tests/unit/data/storage/test_storage_last_seen.py` - Watermark storage
    - `tests/unit/data/storage/test_storage_llm_batch.py` - LLM batch commit flow
    - `tests/unit/data/storage/test_storage_news.py` - News storage and deduplication
    - `tests/unit/data/storage/test_storage_prices.py` - Price storage validation
    - `tests/unit/data/storage/test_storage_queries.py` - Query helpers
    - `tests/unit/data/storage/test_storage_types.py` - Type conversions
    - `tests/unit/data/storage/test_storage_url.py` - URL normalization

  - `tests/unit/utils/` - Utility module tests
    - `tests/unit/utils/test_http.py` - HTTP retry helper tests
    - `tests/unit/utils/test_market_sessions.py` - Market session classification tests
    - `tests/unit/utils/test_retry.py` - Generic retry logic tests
    - `tests/unit/utils/test_symbols.py` - SYMBOLS parsing/validation helpers

  - `tests/unit/workflows/` - Workflow orchestration tests
    - `tests/unit/workflows/test_poller.py` - DataPoller orchestration tests

  - `tests/unit/analysis/` - Analysis module tests
    - `tests/unit/analysis/test_news_classifier.py` - News classification tests
    - `tests/unit/analysis/test_urgency_detector.py` - Urgency detection tests

- `tests/integration/` - Integration tests (organized by workflow)
  - `tests/integration/data/` - Data pipeline tests
    - `tests/integration/data/test_roundtrip_e2e.py` - Full end-to-end pipeline
    - `tests/integration/data/test_dedup_news.py` - Cross-provider deduplication
    - `tests/integration/data/test_timezone_pipeline.py` - UTC conversion validation
    - `tests/integration/data/test_decimal_precision.py` - Decimal handling through storage
    - `tests/integration/data/test_schema_constraints.py` - Schema constraint enforcement
    - `tests/integration/data/test_wal_sqlite.py` - WAL mode behavior
    - `tests/integration/data/providers/test_finnhub_live.py` - Live Finnhub API smoke (network-marked)

  - `tests/integration/llm/` - LLM integration tests
    - `tests/integration/llm/conftest.py` - `ProviderSpec` dataclass and `provider_spec` fixture to parametrize LLM providers
    - `tests/integration/llm/contracts/` - Shared workflow contract suites
      - `tests/integration/llm/contracts/test_llm_code_tools_contract.py` - Validates code tool parity when tooling is toggled
      - `tests/integration/llm/contracts/test_llm_connection_contract.py` - Confirms provider connectivity and baseline generation
      - `tests/integration/llm/contracts/test_llm_web_search_contract.py` - Verifies web search tooling matches Wikipedia featured article lookup
    - `tests/integration/llm/helpers.py` - Shared helpers (`extract_hex64`, `fetch_featured_wiki`, etc.)
    - Notes: Requires API keys; uses Wikipedia with descriptive `User-Agent`; expect flaky network

## Database Schema
Tables (WITHOUT ROWID):
- `news_items(symbol, url, headline, content, published_iso, source, created_at_iso)` — PK: (symbol, url)
- `news_labels(symbol, url, label, created_at_iso)` — PK: (symbol, url); FK → news_items(symbol, url)
- `price_data(symbol, timestamp_iso, price TEXT, volume, session, created_at_iso)` — PK: (symbol, timestamp_iso)
- `analysis_results(symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json, created_at_iso)` — PK: (symbol, analysis_type)
- `holdings(symbol, quantity TEXT, break_even_price TEXT, total_cost TEXT, notes, created_at_iso, updated_at_iso)` — PK: symbol
- `last_seen(key, value)` — Watermarks (`news_since_iso`, `llm_last_run_iso`, `macro_news_min_id`)

Constraints: NOT NULL on required fields, CHECK constraints for positive values, enum validations, JSON object validation for JSON columns
