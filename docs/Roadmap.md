# Trading Bot Development Roadmap

## Project Goal
Automated trading bot that uses LLMs for fundamental analysis. Polls data every 5 minutes, flags urgent events, and issues HOLD/SELL recommendations via scheduled LLM analysis.

## Core Strategy
- Target: Retail traders (not HFT)
- Edge: LLM scans hundreds of sources 24/7
- Scope: Monitor existing positions only (no new discovery)

## Market & Tech Specs
- Market: US equities (NYSE/NASDAQ); US-listed stocks only
- Sessions (ET): Pre 4:00–9:30, Regular 9:30–16:00, Post 16:00–20:00
- Timezone: Store UTC (ISO Z); convert to ET for logic; session enum {REG, PRE, POST}
- Data Sources: Finnhub, Polygon.io, SEC EDGAR, RSS, Reddit

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

**Status**: Production-ready

---

## v0.2 — Core Infrastructure ✅
**Goal**: Build data storage foundation

**Achieves**:
- Strict data models (NewsItem, PriceData, AnalysisResult, Holdings)
- SQLite with WAL mode, JSON1 constraints, deduplication
- URL normalization for cross-provider dedup
- Decimal precision for financial values

**Environment**: Requires SQLite JSON1 extension (fails fast if missing)

**Status**: Complete with full test coverage

---

## v0.3 — Data Collection Layer 📡
**Goal**: Build complete data ingestion pipeline

### v0.3.1 — First Market Connection
**Components**:
- Finnhub provider (news + prices)
- HTTP helper with retry (`utils/http.get_json_with_retry`)
- Basic poller for 5-minute data collection
- Config package for API keys

**Watermark System**:
- State table: `last_seen(key PRIMARY KEY, value)`
- `news_since_iso`: Track last fetched news publish time (incremental fetching)
- `llm_last_run_iso`: Track LLM cutoff for cleanup (prep for v0.5)
- Two-clock design: Fetch by publish time, cleanup by insert time (handles late arrivals)
- 2-minute safety buffer for clock skew

**Data Flow**:
- 5-min loop: Read watermark → Fetch incremental → Store → Update watermark
- Cleanup prep: Define cutoff = T - 2min, process rows where `created_at_iso ≤ cutoff`
- One global `news_since_iso` acceptable for v0.3.1 (per-provider later)

**Success**: Manual script fetches data every 5 minutes with deduplication

**Cost**: $0 (Finnhub free tier)

### v0.3.2 — Multi-Source Collection
**Achieves**:
- RSS provider for additional news
- Urgent keyword detection (bankruptcy, SEC investigation, etc.)
- Cross-source deduplication working
- Enhanced poller for multi-source orchestration

**Flow**: Every 5 min → fetch incremental → dedup → store → filter urgent

### v0.3.3 — Complete Data Pipeline
**Achieves**:
- Polygon.io (backup market data, 5 calls/min free)
- Reddit sentiment (PRAW, ~100 queries/min)
- SEC EDGAR (filings/insider trades, 10 req/sec)
- Circuit breakers and retry logic
- Data quality validation

**Provider Pattern**: Dual providers (news+price) or single-purpose

**Cost**: Free $0 / Recommended ~$50 (Finnhub paid) / Premium ~$150

---

## v0.4 — Cloud Automation ☁️
**Goal**: Move complete system to 24/7 cloud operation

**Achieves**:
- GitHub Actions workflow (5-min cron)
- Database commits to repository
- Secrets management for API keys
- Call `finalize_database()` before commits (WAL checkpoint)

**Success**: Runs autonomously on GitHub infrastructure

**Cost**: $0 (GitHub free tier)

---

## v0.5 — Trading Intelligence Layer 🧠
**Goal**: Add LLM-powered analysis and decisions

**Pipeline**:
```
30-min raw batches → Specialist LLMs → Persistent analysis → Head Trader LLM → HOLD/SELL
```

**Roles**:
- News Analyst
- Sentiment Analyst  
- SEC Filings Analyst
- Head Trader (synthesizes + portfolio context)

**Strategy**: 
- Sort-and-rank approach (not numeric scoring)
- Urgent keywords trigger immediate analysis
- Cleanup on success, preserve on failure

**Success**: Generates actionable trading recommendations

---

## v1.0 — Production Trading Bot 🎯
**Goal**: Complete, reliable trading system

**Achieves**:
- Production monitoring and health checks
- **Logging framework**: Module-level loggers in all providers
- Circuit breakers and redundant failover
- Performance metrics beating buy-and-hold
- 99%+ collection uptime

**Cost**: $10-50/month operational

**Success**: Reliable, profitable recommendation engine

---

## Data Flow Architecture

### Watermark System
**Keys in `last_seen` table**:
- `news_since_iso`: Last news publish time fetched (providers use for incremental)
- `llm_last_run_iso`: Last LLM cutoff processed (for cleanup after success)

### Processing Timeline
**Example flow**:
- 10:00Z: Fetch news published ≥ 09:55Z (using `news_since_iso`)
- 10:30Z: LLM starts, calculates cutoff = 10:28Z (T - 2min buffer)
- 10:32Z: LLM succeeds → set `llm_last_run_iso = 10:28Z`, delete rows ≤ cutoff
- Late arrivals after cutoff remain for next batch

### Design Benefits
- No refetching (incremental via publish time)
- No data loss (2-min buffer for late/skewed items)
- Bounded database size (cleanup after LLM success)
- Separate clocks: fetch by publish time, cleanup by insert time

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