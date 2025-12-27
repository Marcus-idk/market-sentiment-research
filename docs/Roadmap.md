# Market Sentiment Analyzer Development Roadmap

## Instructions for Updating Roadmap
- Read the WHOLE document before making any updates.
- Keep the pattern exactly the same across sections:
  - Required subsections: Goal, Achieves
  - Optional subsection: Notes (add only when clarifications are needed)
  - No other subsection headers allowed (e.g., Success, Environment, Flow, Pipeline, Roles, Strategy). Put that info under Notes if needed.
  - Indicate completion ONLY by adding a ✅ in the section title (e.g., `## v0.2 — Core Infrastructure ✅`).
  - Do NOT add separate lines like "Status: ..." anywhere.
  - For planned/future sections, keep the themed emoji in the title (☁️, 🧠, 🎯) without a ✅.
  - Maintain consistent formatting and structure throughout.
  - Use ✅ only when the entire section is complete.
 - Project-wide explanations of overall behavior belong at the end of this file (bottom). Keep them high-level (e.g., Runtime Flow Snapshot and a short Processing Example). Do not include implementation details there (e.g., schema keys, internal tables, or design-benefit bullets).

## Project Goal
Automated Market Sentiment Analyzer that uses LLMs for fundamental analysis. Polls data every 5 minutes, flags urgent events, and issues HOLD/SELL recommendations via scheduled LLM analysis.

## Core Strategy
- Target: Retail traders (not HFT)
- Edge: LLM scans hundreds of sources 24/7
- Scope: Monitor existing positions only (no new discovery)

---

## v0.1 — LLM Foundation ✅
**Goal**: Establish AI communication layer

**Achieves**:
- LLM provider integrations (OpenAI with reasoning support, Gemini 2.5 Flash)
- Clean provider pattern with async implementation
- SHA-256 validation tests

---

## v0.2 — Core Infrastructure ✅
**Goal**: Build data storage foundation

**Achieves**:
- Strict data models (NewsItem, PriceData, AnalysisResult, Holdings)
- SQLite with WAL mode, JSON1 constraints, deduplication
- URL normalization for cross-provider dedup
- Decimal precision for financial values

**Notes**:
- Requires SQLite JSON1 extension.

---

## v0.3 — Data Collection Layer ✅
**Goal**: Build complete data ingestion pipeline
 
**Achieves**:
- 5‑minute poller ingesting Finnhub news and prices
- Incremental fetching via watermarks with cross‑source deduplication
- Local database UI for inspection and debugging
- Multi‑source orchestration groundwork (company + macro news)
- Extensible provider pattern for upcoming integrations

### v0.3.1 — First Market Connection ✅
**Goal**:
- Establish first market data connection (Finnhub)

**Achieves**:
- Finnhub provider (news + prices)
- HTTP helper with retry (`utils/http.get_json_with_retry`)
- Basic poller for 5-minute data collection
- Config package for API keys
- Centralized Finnhub API validation in client (providers delegate)

**Notes**:
- 5‑min loop: plan cursors from `last_seen_state`, fetch, store, update watermarks.


### v0.3.2 — Database UI ✅
**Goal**: Browse the SQLite database locally and prepare analysis extension points

**Achieves**:
- Run a minimal Streamlit UI for quick local inspection
- Simple news-importance stub marks all news entries important before storage; full LLM-based classification remains planned for v0.5

**Notes**:
- Local-only Streamlit viewer for quick DB inspection.

### v0.3.3 — Macro News ✅
**Goal**:
- Add macro news with independent watermark

**Achieves**:
- Finnhub macro news via `/news?category=general` with `minId` cursor
- Independent global ID-based watermark tracked in `last_seen_state` for Finnhub macro stream
- Poller integrates macro news alongside company news in the 5‑min loop
- Urgency detection stub logs cycle stats but returns no flagged items (empty list); LLM-based detection deferred to v0.5

**Notes**:
- Flow: Every 5 min → fetch, dedup, store, classify urgency (stub).

### v0.3.4 — Complete Data Pipeline ✅
**Goal**:
- Complete ingestion with multi-source news and price dedup framework

**Achieves**:
- Polygon.io news providers (company + macro) for multi-source news coverage
- Price deduplication framework (ready for multiple providers)
- Reddit sentiment ingestion (PRAW, ~100 queries/min; posts + top comments for held symbols)
- Retry logic for external APIs
- Data quality validation

**Notes**:
- Dual news/price provider pattern with shared contract tests; price dedup stores primary provider price and logs mismatches.

---

## v0.4 — Cloud Automation ☁️
**Goal**: Move complete system to 24/7 cloud operation

**Achieves**:
- GitHub Actions workflow (5-min cron)
- Database commits to repository
- Secrets management for API keys
- Call `finalize_database()` before commits (WAL checkpoint)

**Notes**:
 


---

## v0.5 — Market Intelligence Layer 🧠
**Goal**: Add LLM-powered analysis and decisions

**Achieves**:
- LLM analysis pipeline producing HOLD/SELL with justifications
- Urgent-triggered immediate analysis for critical events
- Persistent storage of analysis results and decisions
 
**Notes**:
- Pipeline: 30‑min raw batches → Specialist LLMs → Persistent analysis → Head Trader LLM → HOLD/SELL
- Roles: News Analyst; Sentiment Analyst; SEC Filings Analyst; Head Trader (synthesizes + portfolio context)
- Strategy: Sort‑and‑rank approach (not numeric scoring); urgent keyword detection triggers immediate analysis; cleanup on success, preserve on failure
 
---

## v1.0 — Production Market Sentiment Analyzer 🎯
**Goal**: Complete, reliable market system

**Achieves**:
- Production monitoring and health checks
- **Logging framework**: Module-level loggers in all providers
- Circuit breakers and redundant failover
- Performance metrics beating buy-and-hold
- 99%+ collection uptime

**Notes**:
 

---

## Future Explorations

### Multi-Agent Answer Refinement
- 4 agents answer independently
- Each refines after seeing others
- Judge model picks best or synthesizes
- Reduces single-model bias

### Judge Rubric (0-5 scoring):
- Correctness: aligns with facts
- Evidence use: cites data/IDs
- Logical validity: clear reasoning
- Completeness: covers key angles
- Calibration: appropriate confidence

### Advanced Features
- Local ML filtering before LLM
- Options flow analysis
- Cross-market correlations
- Risk management framework

### Hybrid Data Collection
- WebSocket + REST API mixing (real-time streams + polling fallback)
- Flat file support where necessary (CSV exports, bulk historical data)
- Provider abstraction over multiple transport types

### SEC EDGAR & RSS Ingestion
- SEC EDGAR (filings/insider trades, 10 req/sec)
- RSS feeds (custom news sources)

## Runtime Flow Snapshot
- Startup
  - Loads `.env`, configures logging, and reads `SYMBOLS`, `POLL_INTERVAL`, `DATABASE_PATH` (default `data/database/market_sentiment_analyzer.db`), and provider keys (`FINNHUB_API_KEY`, `POLYGON_API_KEY`, Reddit credentials); if `-v`, also reads `STREAMLIT_PORT`.
  - Ensures the database directory exists and runs `init_database`, which enforces SQLite JSON1 support and applies required PRAGMAs.
  - If `-v`, launches the optional Streamlit UI pointed at the same `DATABASE_PATH`; on failure, logs a warning and continues without UI.
  - Creates configured providers (Finnhub company/macro/price; Polygon company/macro; Reddit social sentiment) and validates each API connection; failures abort startup.
  - Registers graceful shutdown handlers, logs a startup banner, and enters the polling loop.
- Every poll (interval ≈ `POLL_INTERVAL`, e.g., 300s; first cycle runs immediately)
  - Watermark planning:
    - `WatermarkEngine` reads `last_seen_state` and builds per-provider cursor plans using typed rules (timestamp vs ID, GLOBAL vs SYMBOL scope) and provider settings for first-run lookback windows; providers then apply their own overlap windows when constructing API calls.
  - Fetch company and macro news (providers run concurrently):
    - Finnhub company: per-symbol timestamp cursors; each symbol uses its own watermark minus an overlap, or a first-run lookback window when no watermark exists.
    - Finnhub macro: global ID cursor via `minId`; on first run uses a time-based lookback window and tracks `last_fetched_max_id`, which becomes the committed ID watermark.
    - Polygon company: global timestamp cursor with optional per-symbol bootstrap overrides for new or stale symbols; applies overlap and first-run windows and follows pagination via `cursor` / `next_url`.
    - Polygon macro: global timestamp cursor only; applies overlap and first-run windows and follows the same pagination pattern.
  - Fetch social sentiment:
    - Reddit social: per-symbol timestamp cursors via `WatermarkEngine`; bootstrap runs use a wider `time_filter` and lookback window, incremental runs use a narrower `time_filter` with overlap, and each symbol fetches posts and top comments from `stocks+investing+wallstreetbets`.
  - Fetch prices:
    - Finnhub prices: calls `/quote` per symbol, normalizes timestamps to UTC, and classifies each observation into `PRE`, `REG`, `POST`, or `CLOSED` using ET market hours and the NYSE calendar.
  - Store results and run stub analysis:
    - News, social, and price fetches are aggregated per provider; individual provider failures are logged and counted but do not stop other providers.
    - News: a simple importance stub sets `is_important=True` on all news entries; storage keeps one row per article URL and per-symbol links with their importance flags.
    - Social: Reddit discussions are upserted with their source, symbol, community, title, URL, content, and timestamps preserved.
    - Urgency: news and social urgency detectors run as stubs, logging basic stats and returning no urgent items.
    - Prices: `DataPoller._process_prices` treats the first configured price provider as primary, stores only its price per symbol, and logs warnings for missing prices and errors for cross-provider mismatches ≥ $0.01.
  - Watermark commit:
    - For each news and social provider, `WatermarkEngine.commit_updates` runs after storage to advance timestamp or ID watermarks in `last_seen_state` based on the data actually stored, including optional per-symbol marks for GLOBAL+bootstrap providers.
  - Sleep until next cycle:
    - Logs per-cycle stats (news, social, prices, errors) and waits just long enough so that each loop boundary aligns with the configured `POLL_INTERVAL`, unless a shutdown signal or `stop()` request ends the loop.
