# TradingBot — Concise Overview

## Core Idea
Automated US equities bot that polls data sources, stores all timestamps in UTC, runs LLM-based analysis, and makes trading decisions using US/Eastern (ET) session logic. Storage is SQLite with strict constraints and deduplication.

## Time Policy
- Persistence: UTC everywhere (ISO `YYYY-MM-DDTHH:MM:SSZ`).
- Trading logic: Convert UTC to US/Eastern for session-aware decisions (REG, PRE, POST).

## Project Structure
- `config/` — typed settings per provider (data + LLM) and optional env loader.
- `data/` — data models, base abstractions, SQLite schema and storage ops, docs.
- `llm/` — LLM provider base + OpenAI/Gemini implementations and docs.
- `tests/` — model validation, storage CRUD, schema constraints, base-class contracts, LLM connectivity (skips without keys).

## Data Module

### Enums
- `Session`: `REG | PRE | POST` — trading sessions.
- `Stance`: `BULL | BEAR | NEUTRAL` — analysis stance.
- `AnalysisType`: `news_analysis | sentiment_analysis | sec_filings | head_trader`.

### Models (dataclasses)
- `NewsItem(symbol: str, url: str, headline: str, published: datetime, source: str, content: Optional[str])`
  - Purpose: Financial news item.
  - Behavior: Trims strings; validates `url` scheme http/https; normalizes `published` → UTC.

- `PriceData(symbol: str, timestamp: datetime, price: Decimal, volume: Optional[int] = None, session: Session = Session.REG)`
  - Purpose: Price/market datapoint.
  - Behavior: Trims `symbol`; `timestamp` → UTC; `price > 0`; `volume >= 0` if set; `session` must be `Session`.

- `AnalysisResult(symbol: str, analysis_type: AnalysisType, model_name: str, stance: Stance, confidence_score: float, last_updated: datetime, result_json: str, created_at: Optional[datetime] = None)`
  - Purpose: Persistent LLM analysis per symbol/type.
  - Behavior: Trims; JSON must be valid object; `0.0 ≤ confidence_score ≤ 1.0`; `last_updated/created_at` → UTC.

- `Holdings(symbol: str, quantity: Decimal, break_even_price: Decimal, total_cost: Decimal, notes: Optional[str] = None, created_at: Optional[datetime] = None, updated_at: Optional[datetime] = None)`
  - Purpose: Portfolio position snapshot.
  - Behavior: Trims; `quantity, break_even_price, total_cost > 0`; timestamps → UTC.

### Base Abstractions
- `class DataSource(ABC)`
  - `__init__(source_name: str)` — validates identifier string.
  - `async validate_connection() -> bool` — must not raise; return False on issues.
  - Note: No in-memory fetch timestamp; use DB watermarks in `last_seen`.

- `class NewsDataSource(DataSource)`
  - `async fetch_incremental(since: Optional[datetime]) -> List[NewsItem]`.

- `class PriceDataSource(DataSource)`
  - `async fetch_incremental(since: Optional[datetime]) -> List[PriceData]`.

- Exceptions: `DataSourceError`, `RateLimitError(DataSourceError)`.

### Storage (`data/storage.py`)
- Helpers
  - `_normalize_url(url: str) -> str` — strips tracking query params for deduplication.
  - `_datetime_to_iso(dt: datetime) -> str` — UTC ISO with `Z`, no micros.
  - `_decimal_to_text(d: Decimal) -> str` — exact precision as TEXT.
  - `last_seen` state: lightweight key/value table for watermarks (`news_since_iso`, `llm_last_run_iso`).

- Database
  - `init_database(db_path: str) -> None` — executes `schema.sql` (WAL, constraints) and requires SQLite JSON1 (fails fast if missing).
  - `finalize_database(db_path: str) -> None` — checkpoints WAL and switches to DELETE journal mode; run before committing/copying the DB in CI so the `.db` contains all writes (no sidecars needed).

- Writes
  - `store_news_items(db_path: str, items: List[NewsItem]) -> None` — INSERT OR IGNORE by `(symbol, normalized_url)`.
  - `store_price_data(db_path: str, items: List[PriceData]) -> None` — INSERT OR IGNORE by `(symbol, timestamp_iso)`.
  - `upsert_analysis_result(db_path: str, result: AnalysisResult) -> None` — upsert by `(symbol, analysis_type)`; preserves initial `created_at`.
  - `upsert_holdings(db_path: str, holdings: Holdings) -> None` — upsert by `symbol`; preserves `created_at`, updates `updated_at`.
  - `commit_llm_batch(db_path: str, cutoff: datetime) -> Dict[str, int]` — atomic prune: set `llm_last_run_iso=cutoff` and delete `news_items/price_data` where `created_at_iso ≤ cutoff`.

- Reads
  - `get_news_since(db_path: str, timestamp: datetime) -> List[Dict]` — ordered by `published_iso`.
  - `get_price_data_since(db_path: str, timestamp: datetime) -> List[Dict]` — ordered by `timestamp_iso`.
  - `get_all_holdings(db_path: str) -> List[Dict]` — ordered by `symbol`.
  - `get_analysis_results(db_path: str, symbol: str | None = None) -> List[Dict]` — optional filter; ordered by `symbol, analysis_type`.

### Schema (`data/schema.sql`)
- Tables (WITHOUT ROWID):
  - `news_items(symbol, url, headline, content, published_iso, source, created_at_iso)` — PK `(symbol, url)`.
  - `price_data(symbol, timestamp_iso, price TEXT, volume INTEGER, session TEXT, created_at_iso)` — PK `(symbol, timestamp_iso)`.
  - `analysis_results(symbol, analysis_type, model_name, stance, confidence_score, last_updated_iso, result_json, created_at_iso)` — PK `(symbol, analysis_type)`.
  - `holdings(symbol, quantity TEXT, break_even_price TEXT, total_cost TEXT, notes, created_at_iso, updated_at_iso)` — PK `symbol`.
  - `last_seen(key, value)` — persistent watermarks for ingestion/pruning.
- Constraints: NOT NULLs; `price/quantity/break_even_price/total_cost > 0`; `volume >= 0 or NULL`; enums limited; JSON object validation; WAL mode enabled.

## LLM Module

### Base
- `class LLMProvider(ABC)`
  - `__init__(api_key: str, **kwargs)` — stores API key and provider config.
  - `async generate(prompt: str) -> str` — abstract.
  - `async validate_connection() -> bool` — abstract.

### OpenAI
- `class OpenAIProvider(LLMProvider)`
  - Init params: `api_key: str`, `model_name: str`, `temperature: Optional[float] = None`, `reasoning: Optional[Dict] = None`, `tools: Optional[List[Dict]] = None`, `tool_choice: Optional[str | Dict] = None`, `**kwargs` (e.g., `max_output_tokens`, `top_p`).
  - Methods: `async generate(prompt: str) -> str` (Responses API; returns text), `async validate_connection() -> bool`.

### Gemini
- `class GeminiProvider(LLMProvider)`
  - Init params: `api_key: str`, `model_name: str`, `temperature: Optional[float] = None`, `tools: Optional[List[Dict]] = None`, `tool_choice: Optional[str] = None`, `thinking_config: Optional[Dict] = None`, `**kwargs` (e.g., `response_mime_type`).
  - Methods: `async generate(prompt: str) -> str` (text + tool outputs), `async validate_connection() -> bool`.

## Tests (high level)
- Layout: unit tests under `tests/unit/`, integration tests under `tests/integration/` (e.g., LLM providers in `tests/integration/llm/`, data integration tests in `tests/integration/data/`). Shared fixtures live in `tests/conftest.py` and `tests/fixtures/`.
- Markers: `integration` and `network` markers are registered in `pytest.ini`.
  - Run unit only: `pytest -m "not integration and not network"`
  - Run integration/network: `pytest -m "integration or network"`
- Models: field validation, enums, UTC normalization.
- Storage: CRUD, type conversions, deduplication, WAL behavior.
- Schema: NOT NULL/CHECK/PK constraints, JSON object, defaults, WITHOUT ROWID.
- Base classes: DataSource contracts and exceptions.
- LLM: provider connectivity/tool behavior (requires API keys; see tests/integration/llm/).
- Data Integration: organized into focused test files:
  - `test_roundtrip_e2e.py` — complete data flow and cross-model consistency; includes upsert invariants and duplicate prevention
  - `test_dedup_news.py` — URL normalization and cross-provider deduplication
  - `test_timezone_pipeline.py` — UTC timezone handling throughout pipeline (generic timezone conversion; not a DST semantics test)
  - `test_decimal_precision.py` — financial precision preservation with extreme values
  - `test_schema_constraints.py` — database constraint validation and rollback
  - `test_wal_sqlite.py` — WAL mode functionality and concurrent operations

Notes:
- Async tests require `pytest-asyncio` (ensure it is installed).
- SQLite JSON1 is required by `init_database`; ensure your Python/SQLite has JSON1 (e.g., `pysqlite3-binary` on Windows).

## Providers (v0.2.1)

### Finnhub Integration ✅
- `data/providers/finnhub.py` — Complete Finnhub API integration
- Classes:
  - `FinnhubClient` — HTTP wrapper with retry logic for 429/5xx errors, authentication, and timeouts
  - `FinnhubNewsProvider(NewsDataSource)` — Fetches company news from `/company-news` endpoint
  - `FinnhubPriceProvider(PriceDataSource)` — Fetches real-time quotes from `/quote` endpoint
- Features:
  - Incremental news fetching with UTC date ranges and client-side filtering
  - Real-time price quotes with Decimal precision for financial data
  - Proper error handling (auth failures don't retry, server errors retry with jittered backoff)
  - URL validation and article filtering (skips invalid headlines, URLs, timestamps)
  - UTC timestamp normalization throughout
  - Symbol-based data fetching for configured stock lists

## Next Steps
- Add scheduler in `data/scheduler.py` to orchestrate polling and storage
- Implement RSS provider for additional news sources (v0.2.3)
- Add timezone helpers for UTC↔US/Eastern when implementing trading/session logic
