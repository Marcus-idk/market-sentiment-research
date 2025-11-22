# Trading Bot Development Roadmap

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
Automated trading bot that uses LLMs for fundamental analysis. Polls data every 5 minutes, flags urgent events, and issues HOLD/SELL recommendations via scheduled LLM analysis.

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
- Environment: Requires SQLite JSON1 extension (fails fast if missing)

---

## v0.3 — Data Collection Layer
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
- Watermark system:
  - Normalized state table: `last_seen_state(provider, stream, scope, symbol, timestamp, id)` keyed by provider/stream/scope/symbol
  - Enums: provider (`FINNHUB`), stream (`COMPANY`/`MACRO`), scope (`GLOBAL`/`SYMBOL`) keep cursor identities stable
  - Two-clock design: Fetch by publish/published time; cleanup by insert time via batch pruning (handles late arrivals)
- Data flow:
  - 5‑min loop: Build cursor plans from `last_seen_state` → Fetch incremental data from providers → Store → Commit updated watermarks
  - Cleanup prep: choose a cutoff and prune rows where `created_at_iso ≤ cutoff` using batch helpers
 

### v0.3.2 — Database UI ✅
**Goal**: Browse the SQLite database locally and prepare analysis extension points

**Achieves**:
- Run a minimal Streamlit UI for quick local inspection
- Classification extension point stub kept for future LLM use (no label storage)

**Notes**:
- Dev UX: `pip install streamlit` (or `pip install -r requirements-dev.txt`)
- Run: `streamlit run ui/app_min.py`
- Scope: local development (read‑only table viewer); do not expose publicly

### v0.3.3 — Macro News ✅
**Goal**:
- Add macro news with independent watermark

**Achieves**:
- Finnhub macro news via `/news?category=general` with `minId` cursor
- Independent global ID-based watermark tracked in `last_seen_state` for Finnhub macro stream
- Poller integrates macro news alongside company news in the 5‑min loop
- Urgency detection stub logs cycle stats but returns no flagged items (empty list); LLM-based detection deferred to v0.5

**Notes**:
- Flow: Every 5 min → fetch incremental → dedup → store → classify urgency (stub)

### v0.3.4 — Complete Data Pipeline
**Goal**:
- Complete ingestion with multi-source news and price dedup framework

**Achieves**:
- Polygon.io news providers (company + macro) for multi-source news coverage
- Price deduplication framework (ready for multiple providers)
- Reddit sentiment (PRAW, ~100 queries/min)
- SEC EDGAR (filings/insider trades, 10 req/sec)
- RSS feeds (custom news sources)
- Circuit breakers and retry logic
- Data quality validation

**Notes**:
- Provider pattern: Dual providers (news+price) or single-purpose
 - Price dedup: Compare to primary; log mismatches >= $0.01; store primary.
 - Contract test harness: Unified tests for client/news/price providers ensuring consistent data quality validation across all sources (delivers on "Data quality validation" achievement)
 - Partial progress: Polygon news providers implemented; price dedup framework in place (single Finnhub provider currently; Polygon price endpoint requires paid plan). Reddit, SEC EDGAR, and RSS integrations remain planned.

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

## v0.5 — Trading Intelligence Layer 🧠
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

## v1.0 — Production Trading Bot 🎯
**Goal**: Complete, reliable trading system

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

## Runtime Flow Snapshot
- Startup
  - Loads `.env` and logging; parses `SYMBOLS`, `POLL_INTERVAL`, `FINNHUB_API_KEY`, `DATABASE_PATH` (default `data/trading_bot.db`). If `-v`, also uses `STREAMLIT_PORT`. Initializes SQLite (JSON1 required).
  - Launches optional Streamlit viewer if requested (`-v`) before provider validation.
  - Creates configured providers (Finnhub company/macro/price; Polygon news) and validates API connections.
- Every poll (interval = `POLL_INTERVAL`, e.g., 300s; first cycle runs immediately)
  - Watermark planning:
    - `WatermarkEngine` builds per-provider cursor plans from `last_seen_state` using typed rules (timestamp vs ID, global vs per-symbol scope, and configurable overlap/first-run windows from provider settings).
  - Fetch company and macro news:
    - Finnhub company: per-symbol timestamp cursors with overlap; first run uses a lookback window from settings.
    - Finnhub macro: global ID cursor via `minId`; first run uses a lookback window and tracks `last_fetched_max_id`.
    - Polygon company/macro: global timestamp cursors with optional per-symbol bootstrap overrides; apply configured overlap/first-run windows and follow pagination.
  - Fetch prices (`/quote` per symbol) and classify session (REG/PRE/POST/CLOSED) from ET.
  - Store results
    - `store_news_items` writes articles once by URL (`news_items`) and per-symbol links (`news_symbols`), preserving per-symbol `is_important` flags.
    - Run urgency detector (stub; returns none; no urgent headlines logged).
    - `DataPoller._process_prices` deduplicates per symbol across providers, logs mismatches, and stores primary prices.
    - `WatermarkEngine.commit_updates` advances timestamp/ID watermarks in `last_seen_state` based on the data actually stored.
  - Sleep until next cycle.
