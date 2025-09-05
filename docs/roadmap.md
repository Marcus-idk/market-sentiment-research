# Trading Bot Development Plan (Concise)

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
- Pre-1.0 semantic style: `0.1.x` = LLM foundation, `0.2.x` = core data infra and ingestion, `0.3.x` = trading intelligence layer.
- Use patch-level increments like `0.2.1`, `0.2.2`, etc. Avoid ambiguous labels like `0.21`.
- Constraint: Do not change feature scope of `v0.1` and `v0.2` (already completed).

---

## v0.1 — LLM Foundation ✅
- LLM provider module (abstract base + clean provider pattern)
- Providers: GPT-5 (final decisions), Gemini 2.5 Flash (specialists)
- Async implementation + SHA-256 validation tests
- Status: Production-ready

---

## v0.2 — Core Infrastructure ✅
- Data models: NewsItem, PriceData, AnalysisResult, Holdings (strict validation)
- Storage: SQLite schema (4 tables, WAL, constraints) + CRUD, URL normalization, DB-level dedup (INSERT OR IGNORE, natural PKs)
- Environment: Requires SQLite JSON1 extension (init_database fails fast if missing) to enforce JSON object constraints at the DB level.
- Interfaces: Typed DataSource base classes (DataSource, NewsDataSource, PriceDataSource)
- Enums: Session, Stance, AnalysisType; Decimal precision for finance
- Tests: Model validation; CRUD + type conversions; direct SQL constraint checks
- Extras: Holdings break-even; AnalysisResult JSON validation; expert DB optimizations; URL normalization
- Files (v0.2):
```
data/
├── __init__.py          # Clean exports
├── base.py              # Abstract DataSource + validation
├── models.py            # Dataclasses + enums
├── schema.sql           # SQLite schema (WAL, constraints)
├── storage.py           # CRUD + URL normalization
├── API_Reference.md     # Planned data source APIs
└── providers/           # Placeholder for future APIs
```
- Cost: $0

---

## v0.2.1 — Single API Integration 📡
- Goal: Add Finnhub; local polling only
- Components: Finnhub provider (news + price), minimal HTTP helper (`utils/http.get_json_with_retry`), basic scheduler, config package (API key)
- Success: Connects, fetches, stores locally; dedup works; manual polling
- Data retention + watermarks:
  - Add state table `last_seen(key TEXT PRIMARY KEY, value TEXT NOT NULL)`.
  - Keys now: `news_since_iso` (last ingested news publish time, UTC), `llm_last_run_iso` (last analysis cutoff, UTC).
  - 5‑min loop (continues while LLM runs): read `news_since_iso` → fetch news incrementally → store → upsert `news_since_iso` to max published.
  - 30‑min loop (cutoff snapshot): when starting an analysis at time `T`, compute `cutoff = T − 2m` and read rows with `created_at_iso ≤ cutoff` only. Ingestion does NOT pause.
  - Delete-after-success: only after LLM completes successfully, set `llm_last_run_iso = cutoff` and delete raw rows where `created_at_iso ≤ cutoff`. Rows newer than `cutoff` remain for the next batch.
  - Safety buffer: default 2 minutes to tolerate late/clock-skewed items while maintaining market timeliness; tune if needed.
  - Do not use `analysis_results` timestamps as ingestion watermarks (analysis may be delayed/partial).

  Plain-English summary:
  - `last_seen` remembers two simple time markers so the system knows where it left off.
  - `news_since_iso`: providers only fetch articles published at or after this time to avoid refetching everything.
  - `llm_last_run_iso`: after a successful LLM batch, we prune only rows the LLM definitely processed (those inserted with `created_at_iso` at or before this cutoff).
  - Two clocks on purpose: providers filter by source publish time (`published_iso`), while pruning uses database insert time (`created_at_iso`) so late arrivals are never deleted before being analyzed.
  - Scope (v0.2.1): one global `news_since_iso` for all providers/symbols is acceptable with a 2–3 minute overlap window; later we can switch to per‑provider keys if needed.

  Example timeline:
  - 10:00Z: `news_since_iso = 09:55Z`. Providers fetch published ≥ 09:55Z; DB stores rows and advances `news_since_iso` to the max published (say 10:00Z).
  - 10:30Z: LLM starts; computes `cutoff = 10:28Z`. It processes rows with `created_at_iso ≤ 10:28Z` only.
  - 10:29Z: A late article published at 10:26Z arrives now; its `created_at_iso = 10:29Z`, so it is NOT in this batch.
  - 10:32Z: LLM succeeds → set `llm_last_run_iso = 10:28Z`; delete raw rows where `created_at_iso ≤ 10:28Z`. The 10:29Z row remains for the next batch.
- Files (adds to v0.2):
```
config/
└── providers/
    └── finnhub.py        # FinnhubSettings

data/
├── scheduler.py          # 5‑min + 30‑min loops; watermark updates
└── providers/
    └── finnhub.py        # News + Price providers
```
- Schema changes:
  - `data/schema.sql`: add `CREATE TABLE IF NOT EXISTS last_seen (key TEXT PRIMARY KEY, value TEXT NOT NULL);`
  - Keep WAL and JSON1 requirement (init fails fast if JSON1 missing).
- Cost: $0 (Finnhub free tier)

---

## v0.2.2 — GitHub Actions Automation ☁️
- Goal: Cloud execution; 5-min cron
- Components: GH Actions workflow; commit SQLite to repo; secrets for keys
- Success: Runs every 5 min; cloud fetch; DB persists; 24/7; no local runs
- Files:
```
data/ (as v0.2.1)
config/ (GH secrets integration via env)

.github/workflows/trading-bot.yml  # 5-min polling + commit DB
```
- CI note: Call `finalize_database(db_path)` before committing the DB so recent writes in WAL are checkpointed into the main `.db` and sidecar files aren’t needed.
- Cost: $0 (GH free tier)

---

## v0.2.3 — Complete Basic System 🎯
- Goal: Second source + filtering
- Components: RSS provider; keyword filtering (urgent); enhanced scheduler; UTC standardization
- Success: Finnhub + RSS; urgent detection; cross-source dedup; end-to-end ready; unblock LLM (v0.3)
- Files (adds to v0.2.2):
```
data/
├── filters.py           # is_urgent(), URGENT_KEYWORDS
├── scheduler.py         # Multi-source
└── providers/rss.py     # feedparser, pub-date compare
```
- Flow:
```
Every 5 min: scheduler → providers.fetch_incremental(last_seen)
→ convert to models → dedup → storage → filters.is_urgent()
→ urgent: trigger LLM | normal: batch for 30 min

Every 30 min: LLMs process batch → update analysis_results
→ success: delete raw | failure: keep raw for retry
```
- Provider responsibilities: API comms; convert to models; UTC timestamps; incremental fetch
- Pattern:
```python
# Dual (news + price)
class FinnhubNewsProvider(NewsDataSource):
    async def fetch_incremental(self) -> List[NewsItem]: ...
class FinnhubPriceProvider(PriceDataSource):
    async def fetch_incremental(self) -> List[PriceData]: ...

# Single-purpose (news only)
class RSSNewsProvider(NewsDataSource):
    async def fetch_incremental(self) -> List[NewsItem]: ...
class RedditSentimentProvider(NewsDataSource):
    async def fetch_incremental(self) -> List[NewsItem]: ...
```
- Benefits: Type safety; single responsibility; shared config; independent schedules
- Cost: $0 (free tiers)

---

## v0.2.4 — Complete Data Collection 📊 (Expansion MVP)
- Goal: Add remaining sources + robustness
- Sources:
  - Polygon.io (backup market data): batch queries; 5 calls/min free
  - Reddit (PRAW): retail sentiment; ~100 queries/min non-commercial
  - SEC EDGAR: filings/insider trades; 10 req/sec; REST + XML/JSON
  - Note: SEC is stocks only (no crypto)
- Enhancements: Advanced filtering engine; retries/circuit breakers; perf/health metrics; data quality (cross-source validation, freshness, anomalies)
- Success: All 5 sources working; robust recovery; monitoring; validated data; LLM-ready
- Files (v0.2.4):
```
data/
├── __init__.py          # DataSource, providers, scheduler
├── base.py              # ABC: fetch_incremental(), validate_connection()
├── models.py            # News, Price, Sentiment, Filing
├── config/              # Provider settings; GH secrets via env
├── storage.py           # store_items(), get_items_since()
├── deduplication.py     # is_processed(), mark_processed()
├── filters.py           # Keyword/ML-ready rules
├── scheduler.py         # poll_all_sources(), error handling
├── health_monitor.py    # health + performance
└── providers/
    ├── finnhub.py      # news + price
    ├── polygon.py      # news + price
    ├── rss.py          # news only
    ├── reddit.py       # sentiment as news
    └── sec_edgar.py    # regulatory news

.github/workflows/trading-bot.yml
```
- Cost: Free $0; Recommended ~$50 (Finnhub paid); Premium ~$150 (Finnhub + Polygon)

---

## v0.3.x — Trading Intelligence Layer (Future)
- Pipeline:
```
30-min raw batches → Specialist LLMs → Persistent analysis → Head Trader LLM → HOLD/SELL
```
- Roles: News Analyst; Sentiment Analyst; SEC Filings Analyst; Head Trader (synthesizes + holdings)
- Strategy: Sort-and-rank (not numeric scoring); update per-symbol persistent analysis
- Triggers: Urgent keywords (immediate); scheduled (30 min); cleanup on success; preserve raw on failure; head trader reads persistent analysis
- Trading logic: Portfolio tracking; signal generation; HOLD/SELL engine
- Orchestration: GH Actions; 5-min polling; 30-min LLM; SQLite in-repo; fully cloud; outputs: holdings analysis + recs
- Implementation: Clean architecture; env-based config; SQLite indexes by query patterns; structured logging; integration tests

---

## v1.0 — Complete Trading Bot 🎯 (Final Target)
- Feature set: LLM providers (v0.1); data sources (v0.2+); agents/orchestration/scheduling (v0.3+); production infra (this phase)
- Infra: Rate limiting; lightweight local ML filtering; data validation; circuit breakers; monitoring/health; DB optimization; redundant failover
- Metrics: Beat buy-and-hold; 99%+ collection uptime; $10–$50/month; recommend-only (no auto-execution)
- Stack: Python; GitHub Actions; clean architecture; async I/O

---

## Testing Overview (Current)
- Layout: unit tests under `tests/unit/`; integration tests under `tests/integration/`.
- Markers: `integration`, `network` (see `pytest.ini`).
- Data integration tests (under `tests/integration/data/`):
  - `test_roundtrip_e2e.py` — end-to-end flows; upsert invariants; duplicate prevention
  - `test_dedup_news.py` — URL normalization and cross-provider deduplication
  - `test_timezone_pipeline.py` — UTC handling across pipeline (generic tz conversion)
  - `test_decimal_precision.py` — Decimal precision preservation with extreme values
  - `test_schema_constraints.py` — DB CHECK/enum/JSON constraints and rollback
  - `test_wal_sqlite.py` — WAL mode functionality and concurrent read/write stability
- LLM integration tests live in `tests/integration/llm/` and are gated by API keys.
- JSON1 required: `init_database` fails fast if JSON1 is missing.
