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

## v0.1 — LLM Foundation ✅
- LLM provider module (abstract base + clean provider pattern)
- Providers: GPT-5 (final decisions), Gemini 2.5 Flash (specialists)
- Async implementation + SHA-256 validation tests
- Status: Production-ready

---

## v0.2 — Core Infrastructure ✅
- Data models: NewsItem, PriceData, AnalysisResult, Holdings (strict validation)
- Storage: SQLite schema (4 tables, WAL, constraints) + CRUD, URL normalization, DB-level dedup (INSERT OR IGNORE, natural PKs)
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

## v0.21 — Single API Integration 📡
- Goal: Add Finnhub; local polling only
- Components: Finnhub provider (news + price), basic scheduler, config (API key)
- Success: Connects, fetches, stores locally; dedup works; manual polling
- Files (adds to v0.2):
```
data/
├── config.py            # API keys, local env
├── scheduler.py         # Local polling
└── providers/
    ├── __init__.py
    └── finnhub.py       # News + Price providers
```
- Cost: $0 (Finnhub free tier)

---

## v0.22 — GitHub Actions Automation ☁️
- Goal: Cloud execution; 5-min cron
- Components: GH Actions workflow; commit SQLite to repo; secrets for keys
- Success: Runs every 5 min; cloud fetch; DB persists; 24/7; no local runs
- Files:
```
data/ (as v0.21)
config.py (GH secrets integration)

.github/workflows/trading-bot.yml  # 5-min polling + commit DB
```
- Cost: $0 (GH free tier)

---

## v0.23 — Complete Basic System 🎯
- Goal: Second source + filtering
- Components: RSS provider; keyword filtering (urgent); enhanced scheduler; UTC standardization
- Success: Finnhub + RSS; urgent detection; cross-source dedup; end-to-end ready; unblock LLM (v0.3)
- Files (adds to v0.22):
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

## v0.25 — Complete Data Collection 📊 (Expansion MVP)
- Goal: Add remaining sources + robustness
- Sources:
  - Polygon.io (backup market data): batch queries; 5 calls/min free
  - Reddit (PRAW): retail sentiment; ~100 queries/min non-commercial
  - SEC EDGAR: filings/insider trades; 10 req/sec; REST + XML/JSON
  - Note: SEC is stocks only (no crypto)
- Enhancements: Advanced filtering engine; retries/circuit breakers; perf/health metrics; data quality (cross-source validation, freshness, anomalies)
- Success: All 5 sources working; robust recovery; monitoring; validated data; LLM-ready
- Files (v0.25):
```
data/
├── __init__.py          # DataSource, providers, scheduler
├── base.py              # ABC: fetch_incremental(), validate_connection()
├── models.py            # News, Price, Sentiment, Filing
├── config.py            # All API keys; GH secrets
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

## v0.3+ — Trading Intelligence Layer (Future)
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

