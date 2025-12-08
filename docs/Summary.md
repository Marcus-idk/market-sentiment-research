# Summary.md - Codebase Index for LLMs

## Guide to Updating Summary.md

When updating this file, follow this checklist:
1. **Directory changes**: If new directories are added, document their purpose
2. **File changes**: When files are added/removed, update the file lists under each module
3. **Function/Class changes**: When functions or classes are added/modified/removed, update their entries
4. **Enum changes**: Always document enums with their values as they're database-critical
5. **Keep descriptions brief**: One-line purpose descriptions, focus on WHAT not HOW
6. **Include all public APIs**: Document all functions/classes that other modules import
7. **Test updates**: Keep the test inventory in `docs/Test_Catalog.md`; this file only links to it
8. **Ignore tempFiles/**: Do not flag tempFiles/ directory for updates; it contains temporary planning notes only

---

## Core Idea
Framework for US equities data collection and LLM-ready storage. Current scope: strict UTC models, SQLite with constraints/dedup, LLM provider integrations (OpenAI, Gemini), and a configurable (5 mins for now) data poller with Finnhub, Polygon, and Reddit providers (news, prices, social sentiment). Trading decisions are not implemented yet; session detection is implemented via ET conversion.

## Time Policy
- Persistence: UTC everywhere (ISO `YYYY-MM-DDTHH:MM:SSZ`).
- Sessions: `Session = {REG, PRE, POST, CLOSED}` is available in models. ET conversion and session classification are implemented; providers normalize timestamps to UTC and use `utils.market_sessions.classify_us_session()` to set the session.

## Environment Variables
- `FINNHUB_API_KEY` - Required for market data fetching
- `POLYGON_API_KEY` - Required for Polygon.io news data
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` - Required for Reddit social sentiment
- `OPENAI_API_KEY` - Required for OpenAI LLM provider
- `GEMINI_API_KEY` - Required for Gemini LLM provider
- `DATABASE_PATH` - Optional, defaults to data/trading_bot.db
- `SYMBOLS` - Required for `run_poller.py`; comma-separated tickers (e.g., "AAPL,MSFT,TSLA")
- `POLL_INTERVAL` - Required for `run_poller.py`; polling frequency in seconds (e.g., 300 for 5 minutes)
- `STREAMLIT_PORT` - Optional, defaults to 8501; port used when launching web UI with `-v`
- `LOG_LEVEL` - Optional; logging level name (e.g., DEBUG, INFO)
- `LOG_FILE` - Optional; path to log file (if set, logs also go to this file)
- `LOG_FORMAT` - Optional; logging format string for log lines

## Top-Level Files
- `README.md` - Landing page that points developers to detailed documentation in `docs/`
- `requirements.txt` - Runtime and test dependencies (OpenAI, Gemini, httpx, pytest, etc.)
- `requirements-dev.txt` - Developer-only extras
- `pytest.ini` - Pytest configuration (pythonpath, markers, default flags)
- `.env.example` - Example environment configuration (copy to `.env` and set API keys)

## Main Entry Points
- `run_poller.py` - Main data collection script
  - `PollerConfig` - Configuration dataclass (db_path, symbols, poll_interval, ui_port, finnhub_settings, polygon_settings, reddit_settings)
  - `setup_environment()` - Load environment variables and configure logging
  - `build_config()` - Parse environment variables and build PollerConfig object
  - `initialize_database()` - Initialize database and return success status
  - `launch_ui_process()` - Launch Streamlit UI process if `-v` flag provided
  - `create_and_validate_providers()` - Create and validate news/social/price providers, returns provider lists (news, social, prices)
  - `cleanup_ui_process()` - Terminate UI process on shutdown
  - `main()` - Async entry point with signal handling
  - Uses `utils.logging.setup_logging()` for consistent logging
  - Uses `utils.signals.register_graceful_shutdown()` for SIGINT/SIGTERM
  - Requires `SYMBOLS`, `POLL_INTERVAL`, `FINNHUB_API_KEY`, `POLYGON_API_KEY`, and Reddit credentials (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`) in environment
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
  - `config/providers/reddit.py`
    - `RedditSettings` - Dataclass for Reddit OAuth and polling configuration
    - `RedditSettings.from_env()` - Load Reddit settings from environment

### `data/` — Data models, storage, and providers
**Purpose**: Core data structures, SQLite operations, and data source implementations

**Files**:
- `data/__init__.py` - Public facade (exports base classes, models, and storage operations)
- `data/schema.sql` - SQLite schema definition with constraints

- `data/base.py` - Abstract base classes for data sources
  - `DataSource` - Base class for all data sources; constructor enforces `source_name` as a non-empty string (≤100 chars) and strips whitespace
  - `DataSourceError` - Exception for data source failures
  - `NewsDataSource` - Abstract class for news providers
    - `fetch_incremental(*, since: datetime | None = None, min_id: int | None = None, symbol_since_map: Mapping[str, datetime] | None = None) -> list[NewsEntry]` — unified cursor interface
      - Date-based providers use `since` (ignore `min_id`)
      - ID-based providers use `min_id` (ignore `since`)
      - `symbol_since_map` allows per-symbol cursors that override the global `since` where supported
  - `PriceDataSource` - Abstract class for price providers
    - `fetch_incremental() -> list[PriceData]` — snapshot price fetch (no incremental cursors yet)
  - `SocialDataSource` - Abstract class for social providers
    - `fetch_incremental(*, since: datetime | None = None, symbol_since_map: Mapping[str, datetime] | None = None) -> list[SocialDiscussion]` — timestamp cursors (per-symbol or global)

- `data/models.py` - Core dataclasses and enums
  **Enums**:
  - `AnalysisType` - Types: `news_analysis`, `sentiment_analysis`, `sec_filings`, `head_trader`
  - `NewsType` - News kinds: `macro`, `company_specific`
  - `Session` - Trading sessions: REG, PRE, POST, CLOSED
  - `Stance` - Analysis stances: BULL, BEAR, NEUTRAL
  - `Urgency` - News urgency levels: URGENT, NOT_URGENT

  **Dataclasses**:
  - `AnalysisResult` - `symbol`, `analysis_type` (AnalysisType), `model_name`, `stance` (Stance), `confidence_score` (0–1), `last_updated` (UTC), `result_json` (JSON string), `created_at` (UTC, optional)
  - `Holdings` - `symbol`, `quantity` (Decimal), `break_even_price` (Decimal), `total_cost` (Decimal), `notes` (optional), `created_at`/`updated_at` (UTC, optional)
  - `NewsItem` - Article-level: `url`, `headline`, `published` (UTC), `source`, `news_type` (NewsType), `content` (optional)
  - `NewsSymbol` - Join row: `url`, `symbol`, `is_important` (bool | None)
  - `NewsEntry` - Domain model: `article` (NewsItem), `symbol`, `is_important`
  - `PriceData` - `symbol`, `timestamp` (UTC), `price` (Decimal), `volume` (optional), `session` (Session)
  - `SocialDiscussion` - `source`, `source_id`, `symbol`, `community` (platform section like subreddit/channel), `title`, `url`, `published` (UTC), `content` (optional)

  **Functions**:
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

  - `storage_crud.py` - CRUD operations for all data types
    - **Store**: `store_news_items()` (accepts list[NewsEntry], splits to tables), `store_price_data()`, `store_social_discussions()`
    - **Query**: `get_news_since()` (returns list[NewsEntry]), `get_social_discussions_since()`, `get_news_symbols()`, `get_price_data_since()`, `get_all_holdings()`, `get_analysis_results()`
    - **Upsert**: `upsert_analysis_result()`, `upsert_holdings()`

  - `storage_batch.py` - Batch operations for LLM processing
    - **Batch queries**: `get_news_before()` and `get_prices_before()` - Read news and prices created at or before a cutoff
    - **Batch operations**: `commit_llm_batch()` - Atomically prune processed rows from `news_symbols`, `news_items`, and `price_data` up to a cutoff

  - `storage_watermark.py` - Typed watermark helpers for provider/stream state
    - **Helpers**: `get_last_seen_timestamp()`, `set_last_seen_timestamp()`, `get_last_seen_id()`, `set_last_seen_id()` - Read/write timestamp and ID cursors using strongly-typed enums for provider, stream, and scope

  - `storage_utils.py` - Utilities and type converters
    - **Helpers**: `_datetime_to_iso()`, `_decimal_to_text()`, `_iso_to_datetime()`, `_normalize_url()`
    - **Row converters**: `_row_to_analysis_result()`, `_row_to_holdings()`, `_row_to_news_item()` (article-level), `_row_to_news_symbol()`, `_row_to_news_entry()`, `_row_to_price_data()`, `_row_to_social_discussion()`

**Subdirectories**:
- `data/providers/` - Data source implementations
  - `data/providers/__init__.py` - Public facade; import via `from data.providers import finnhub, polygon, reddit`
  - `data/providers/finnhub/`
    - `FinnhubClient` - HTTP client for Finnhub API with retry logic
      - `__init__()` - Initialize with settings
      - `get()` - Make authenticated GET request with retry logic (path, optional params)
      - `validate_connection()` - Centralized API validation used by providers
    - `FinnhubNewsProvider` - Company news fetching implementation (per-symbol cursors)
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(*, since=..., symbol_since_map=...) -> list[NewsEntry]` - Date-based; applies a configurable overlap window (minutes) and first-run lookback (days) from `FinnhubSettings`
      - `_parse_article()` - Convert API response to NewsEntry (article `news_type=company_specific`, `is_important=True` stub)
    - `FinnhubMacroNewsProvider` - Market-wide macro news fetching implementation (ID-based cursor)
      - `__init__()` - Initialize with settings and symbols (watchlist for filtering)
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(*, min_id=...) -> list[NewsEntry]` - ID-based; uses Finnhub `minId` with configurable first-run lookback (days); tracks `last_fetched_max_id`
      - `_parse_article()` - Convert API response to NewsEntry list per watchlist symbol; fall back to 'MARKET' when none match
      - `_extract_symbols_from_related()` - Filter `related` field against watchlist; if nothing survives, fallback to ['MARKET'] for market-wide coverage
      - `last_fetched_max_id` - Stores latest article ID for watermark updates
    - `FinnhubPriceProvider` - Price quote fetching implementation
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental()` - Fetch current prices for configured symbols (snapshot quotes; no incremental cursor)
      - `_parse_quote()` - Convert API response to PriceData; skips missing/invalid/non-positive quotes; ET-based session detection
  - `data/providers/polygon/`
    - `PolygonClient` - HTTP client for Polygon.io API with retry logic
      - `__init__()` - Initialize with settings
      - `get()` - Make authenticated GET request with retry logic (path, optional params)
      - `validate_connection()` - API validation using market status endpoint
      - `_extract_cursor_from_next_url(next_url)` - Helper to extract `cursor` query param from Polygon `next_url` pagination links
    - `PolygonNewsProvider` - Company news fetching implementation (global cursor with symbol overrides)
      - `__init__()` - Initialize with settings and symbols
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(since=..., symbol_since_map=...) -> list[NewsEntry]` - Date-based; uses a global timestamp cursor with configurable overlap/first-run windows and optional per-symbol bootstrap overrides
      - `_fetch_symbol_news()` - Fetch news for single symbol with pagination until complete
      - `_extract_cursor()` - Extract cursor from Polygon next_url for pagination
      - `_parse_article()` - Convert API response to NewsEntry; parses RFC3339 timestamps; article `news_type=company_specific`, `is_important=True` stub
    - `PolygonMacroNewsProvider` - Market-wide macro news fetching implementation (global timestamp cursor)
      - `__init__()` - Initialize with settings and symbols (watchlist for filtering)
      - `validate_connection()` - Delegates to client
      - `fetch_incremental(since=...) -> list[NewsEntry]` - Date-based; uses configurable overlap/first-run windows and handles pagination
      - `_extract_cursor()` - Extract cursor from Polygon next_url for pagination
      - `_parse_article()` - Convert API response to NewsEntry list per watchlist symbol; default to 'MARKET' when none match
      - `_extract_symbols_from_tickers()` - Filter `tickers` array against watchlist; if nothing survives, fallback to ['MARKET'] for market-wide coverage
  - `data/providers/reddit/`
    - `RedditClient` - PRAW wrapper for OAuth-backed Reddit access; `validate_connection()` calls `/api/v1/me`
    - `RedditSocialProvider` - Social sentiment provider (per-symbol timestamp cursors)
      - `fetch_incremental(*, since=..., symbol_since_map=...) -> list[SocialDiscussion]` — uses subreddit combo `stocks+investing+wallstreetbets`, `time_filter=week` on bootstrap, `time_filter=hour` for incremental, local watermark filtering, and top comments aggregation (limit from settings); fills `community` with subreddit name
      - `_build_content()` - Concatenate post selftext and top comments; tolerant of comment fetch failures

- `data/storage/state_enums.py` - Enums for watermark provider/stream/scope
  - `Provider` - Values: `FINNHUB`, `POLYGON`, `REDDIT`
  - `Stream` - Values: `COMPANY`, `MACRO`, `SOCIAL`
  - `Scope` - Values: `GLOBAL`, `SYMBOL`

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
      - `__init__()` - Configure with model, temperature, tools, tool_choice, thinking_config
        - `tool_choice`: maps to Gemini function-calling modes — `none→NONE`, `auto→AUTO`, `any→ANY`; `"any"` requires `tools` to be provided and any `tool_choice` requires tools with `function_declarations` (built-in tools alone are not enough)
        - Defaults: if `thinking_config` is not provided, the provider sets `{"thinking_budget_token_limit": 128}`; when provided, budgets below 128 are clamped up to 128 to keep a minimum reasoning budget
        - Code execution is opt‑in via `tools=[{"code_execution": {}}]`
      - `generate()` - Send prompt and get response
      - `validate_connection()` - Test API connectivity
      - `_classify_gemini_exception()` - Map SDK errors to retry logic

### `utils/` — Shared utilities
**Purpose**: Cross-cutting concerns like retry logic and HTTP helpers

**Files**:
- `utils/__init__.py` - Package marker

- `utils/datetime_utils.py` - Datetime helpers
  - `normalize_to_utc(dt)` - Normalize naive/aware datetimes to UTC for use in models and workflows
  - `parse_rfc3339(timestamp_str)` - Parse RFC3339/ISO 8601 strings to UTC datetimes

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
  - `parse_symbols(raw, *, filter_to=None, validate=True)` - Parse comma-separated tickers, normalize to upper-case, optionally filter to a watchlist while deduplicating and validating format. Used by `run_poller.py`, Finnhub macro, and Polygon macro news providers.

### `workflows/` — Orchestration layer
**Purpose**: Coordinate data collection, processing, and analysis workflows

**Files**:
- `workflows/__init__.py` - Public facade (exports DataPoller)
- `workflows/poller.py` - Data collection orchestrator
  - `DataPoller` - Orchestrates multiple providers concurrently with urgency detection
    - `__init__(db_path, news_providers, social_providers, price_providers, poll_interval)` - Initialize poller with news, social, and price providers
    - `_fetch_all_data()` - Concurrently fetch news, social discussions, and prices; return company/macro news, social_discussions, and per‑provider prices with errors
    - `_log_urgent_items()` - Log urgent news items to console
    - `_log_urgent_social()` - Log urgent social threads to console
    - `_process_news()` - Store news (NewsEntry split to tables), detect urgency, update watermarks
    - `_process_social()` - Store social discussions, detect urgency, update watermarks for social providers
    - `_process_prices()` - Deduplicate per symbol using primary provider; log mismatches ≥ $0.01; store primary only; skips symbols missing from primary (intentional design, not a bug)
    - `poll_once()` - One cycle: fetch, process, update watermarks, return stats
    - `run()` - Continuous polling loop with interval scheduling and graceful shutdown
    - `stop()` - Request graceful shutdown
  - `DataBatch` (TypedDict) - Batch result with `company_news`, `macro_news`, `social_discussions`, `prices: dict[PriceDataSource, dict[str, PriceData]]` (provider → {symbol → PriceData}), per‑provider maps, and `errors`
  - `PollStats` (TypedDict) - Per-cycle stats with `news`, `social`, `prices`, `errors`

- `workflows/watermarks.py` - Watermark planning and persistence for news and social providers
  - `CursorPlan` - Dataclass describing cursor kwargs (`since`, `min_id`, optional `symbol_since_map`) passed to provider `fetch_incremental` methods
  - `CURSOR_RULES` - Mapping from provider types (Finnhub, Polygon, Reddit) to cursor rules (provider/stream/scope, cursor kind, bootstrap behavior, overlap family)
  - `WatermarkEngine` - Builds per-provider cursor plans from `last_seen_state` and committed data, and writes back updated timestamp/ID watermarks after processing for news and social streams
  - `is_macro_stream(provider)` - Helper to identify macro streams for routing news into `macro_news` vs `company_news`

### `analysis/` — Business logic and classification
**Purpose**: Stubs for news labeling and urgency analysis (LLM-backed flow planned for v0.5)

**Files**:
- `analysis/__init__.py` - Public facade (re-exports news_importance, urgency_detector submodules)
- `analysis/news_importance.py` - News importance stub
  - `label_importance(news_entries)` - Marks all entries as important (stub) and returns the list
- `analysis/urgency_detector.py` - Urgency detection module
  - `UrgencyInput` - Normalized text+metadata payload used for urgency scoring
  - `detect_news_urgency(news_entries)` - Normalizes headline/body and logs stub stats; returns empty list for now
  - `detect_social_urgency(social_items)` - Normalizes title/post/comments and logs stub stats; returns empty list for now

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
- `docs/Test_Catalog.md` - Complete test inventory (files and test functions)
- `docs/Test_Guide.md` - Testing structure, naming conventions, markers, and contract-testing rules
- `docs/Writing_Code.md` - Coding standards, design principles, and review checklist

### `tests/` — Test suite
See `docs/Test_Catalog.md` for the complete test inventory. This summary focuses on source modules and architecture.

## Database Schema
Tables:
- `news_items(url, headline, content, published_iso, source, news_type, created_at_iso)` — PK: url
- `news_symbols(url, symbol, is_important, created_at_iso)` — PK: (url, symbol); FK → news_items(url) ON DELETE CASCADE
- `price_data(symbol, timestamp_iso, price TEXT, volume, session, created_at_iso)` — PK: (symbol, timestamp_iso)
- `analysis_results(symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json, created_at_iso)` — PK: (symbol, analysis_type)
- `holdings(symbol, quantity TEXT, break_even_price TEXT, total_cost TEXT, notes, created_at_iso, updated_at_iso)` — PK: symbol
- `social_discussions(source, source_id, symbol, community, title, url, content, published_iso, created_at_iso)` — PK: (source, source_id)
- `last_seen_state(provider, stream, scope, symbol DEFAULT '__GLOBAL__', timestamp, id)` — Watermarks keyed by provider/stream/scope/symbol; `provider` constrained to `FINNHUB`/`POLYGON`/`REDDIT`, `stream` to `COMPANY`/`MACRO`/`SOCIAL`, `scope` to `GLOBAL`/`SYMBOL`; symbol is non-null with global sentinel; CHECK enforces exactly one of `timestamp` or `id` is set; timestamps stored as ISO text, IDs as integers

Constraints: NOT NULL on required fields, CHECK constraints for positive values, enum validations, JSON object validation for JSON columns
