# Trading Bot Development Roadmap

## Instructions for Updating Roadmap
- Read the WHOLE document before making any updates.
- Keep the pattern exactly the same across sections:
  - Required subsections (exactly these three): Goal, Achieves, Notes
  - No other subsection headers allowed (e.g., Success, Environment, Flow, Pipeline, Roles, Strategy). Put that info under Notes.
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

## Versioning Scheme
- Pre-1.0: Incremental features (0.1.x, 0.2.x, 0.3.x)
- Each minor version = major capability milestone
- Patch versions for fixes and minor improvements

---

## v0.1 — LLM Foundation ✅
**Goal**: Establish AI communication layer

**Achieves**: 
- LLM provider integrations (OpenAI GPT-5, Gemini 2.5 Flash)
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
  - State table: `last_seen(key PRIMARY KEY, value)`
  - `news_since_iso`: Track last fetched news publish time (incremental)
  - `llm_last_run_iso`: Track LLM cutoff for cleanup (prep for v0.5)
  - Two-clock design: Fetch by publish time; cleanup by insert time (handles late arrivals)
  - 2‑minute safety buffer for clock skew (implemented via `FinnhubNewsProvider.fetch_incremental()`)
- Data flow:
  - 5‑min loop: Read watermark → Fetch incremental → Store → Update watermark
  - Cleanup prep: cutoff = T − 2min, process rows where `created_at_iso ≤ cutoff`
  - One global `news_since_iso` acceptable (per‑provider later)
 

### v0.3.2 — Database UI + News Classifier✅
**Goal**: Browse the SQLite database locally and prepare news classification structure

**Achieves**:
- Run a minimal Streamlit UI for quick local inspection
- News classifier stub that returns 'Company' for all items (intentional placeholder until v0.5 LLM layer)
- `news_labels` table structure ready for future LLM-powered classification
- Classification pipeline integrated into poller workflow

**Notes**:
- Dev UX: `pip install streamlit` (or `pip install -r requirements-dev.txt`)
- Run: `streamlit run ui/app_min.py`
- Scope: local development (read‑only table viewer); do not expose publicly

### v0.3.3 — Macro News ✅
**Goal**:
- Add macro news with independent watermark

**Achieves**:
- Finnhub macro news via `/news?category=general` with `minId` cursor
- Independent watermark `macro_news_min_id` tracked in `last_seen`
- Poller integrates macro news alongside company news in the 5‑min loop
- Urgency detection stub logs cycle stats but returns no flagged items (empty list); LLM-based detection deferred to v0.5

**Notes**:
- Flow: Every 5 min → fetch incremental → dedup → store → classify urgency (stub)

### v0.3.4 — Complete Data Pipeline
**Goal**:
- Complete ingestion with dual price providers and dedup

**Achieves**:
- Polygon.io (concurrent price provider, 5 calls/min free tier; fetches alongside Finnhub every cycle)
- Reddit sentiment (PRAW, ~100 queries/min)
- SEC EDGAR (filings/insider trades, 10 req/sec)
- RSS feeds (custom news sources)
- Circuit breakers and retry logic
- Data quality validation

**Notes**:
- Provider pattern: Dual providers (news+price) or single-purpose
 - Price dedup: Compare to primary; log mismatches >= $0.01; store primary.
 - Partial progress: Polygon price provider is implemented; Reddit, SEC EDGAR, and RSS integrations remain planned.


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
  - Load environment and logging, initialize the database, optionally launch the local UI, and validate provider connectivity.
- Poll cycle
  - Read watermarks, fetch news and prices concurrently, store results, classify company news, update watermarks, then sleep until the next interval.
- Example
  - First run: fetch a recent window for each source; next cycle: fetch only items newer than the stored watermark.
