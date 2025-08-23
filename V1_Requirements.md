# Trading Bot Development Plan

## Project Goal
Build an automated trading bot that leverages LLMs for fundamental analysis to gain an edge over retail traders. The bot will poll data sources every 5 minutes, filter for urgent events, and provide hold/sell recommendations via scheduled LLM analysis.

## Core Strategy
- **Target Competition**: Retail traders (not institutional HFT firms)
- **Edge**: LLM analyzing hundreds of sources 24/7 vs manual traders reading 2-3 sources
- **Final Scope**: Monitor existing positions only (no new trade discovery)

## Market Focus & Technical Specifications
- **Target Market**: US Stock Market exclusively (NYSE, NASDAQ)
- **Supported Securities**: US-listed stocks only (no crypto, forex, or international markets)
- **Trading Sessions**: 
  - Pre-market: 4:00 AM - 9:30 AM ET
  - Regular: 9:30 AM - 4:00 PM ET
  - Post-market: 4:00 PM - 8:00 PM ET
- **Timezone Strategy**: 
  - All timestamps stored as UTC in database (ISO format with Z suffix)
  - Convert to Eastern Time (ET) for trading logic and session determination
  - Session enum values (REG, PRE, POST) correspond to US market sessions
- **Data Sources**: US-focused financial data providers (Finnhub, Polygon.io, SEC EDGAR, etc.)

---

## v0.1 - LLM Foundation ✅ **COMPLETED**

### What's Built
- **LLM Provider Module**: Abstract base class with clean provider pattern
- **OpenAI Provider**: GPT-5 with reasoning, tools, function calling
- **Gemini Provider**: Gemini 2.5 Flash with code execution, thinking config
- **Comprehensive Testing**: SHA-256 validation tests for both providers
- **Async Implementation**: Production-ready async/await pattern

### LLM Selection Strategy
- **Gemini 2.5 Flash**: Cost-effective for specialist analyst roles
- **GPT-5**: Premium model for final trading decisions

### Status: ✅ **Production Ready**

---

## v0.2 - Core Infrastructure Foundation 🏗️ **COMPLETED**

### Goal: Build Solid Foundation Without APIs

#### Core Components ✅ **COMPLETED**
- **Data Models**: NewsItem, PriceData, AnalysisResult, Holdings DTOs with comprehensive validation
- **Storage Layer**: Complete SQLite schema + CRUD operations with URL normalization and database-level deduplication
- **Abstract Interface**: Type-safe DataSource base classes (DataSource, NewsDataSource, PriceDataSource)
- **Enum System**: Session, Stance, AnalysisType enums for structured data consistency

#### Success Criteria ✅ **ALL COMPLETED**
- ✅ SQLite database creates tables correctly (4 tables with expert optimizations)
- ✅ Data models with robust validation (timezone handling, positive value checks, JSON validation)
- ✅ Storage operations work (specialized CRUD for each model type)
- ✅ Abstract DataSource interface defined (with proper inheritance hierarchy)
- ✅ Database-level deduplication functional (INSERT OR IGNORE + natural primary keys + URL normalization)

#### Testing Phases ✅ **ALL COMPLETED**
- ✅ **Phase 1 Testing**: Data model validation (__post_init__ validation for all models)
- ✅ **Phase 2 Testing**: Storage operations (CRUD operations, Windows-safe SQLite cleanup, type conversions)
- ✅ **Phase 3 Testing**: Database schema constraints (direct SQL constraint validation, bypassing Python)

#### Advanced Features Implemented (Beyond Original v0.2 Plan)
- **LLM Analysis Models**: AnalysisResult with JSON validation for future LLM integration
- **Portfolio Tracking**: Holdings model with break-even calculations
- **Expert Database Optimizations**: WAL mode, WITHOUT ROWID, CHECK constraints
- **Type Safety**: Comprehensive enum system and Decimal precision for financial data
- **URL Normalization**: Cross-provider deduplication via tracking parameter removal

### File Structure (v0.2) **AS IMPLEMENTED**
```
data/
├── __init__.py          # Clean exports (19 items)
├── base.py              # Abstract DataSource classes with input validation
├── models.py            # @dataclass models: NewsItem, PriceData, AnalysisResult, Holdings + enums
├── schema.sql           # Expert-optimized SQLite schema (4 tables, WAL mode, constraints)
├── storage.py           # Specialized CRUD operations with URL normalization and type conversions
├── API_Reference.md     # Documentation of planned data source APIs
└── providers/           # Directory for future API provider implementations (empty)
```

### Cost: $0 (No APIs yet)

---

## v0.21 - Single API Integration 📡 **PHASE 2**

### Goal: Add Finnhub API, Local Polling Only

#### New Components
- **Finnhub Provider**: HTTP client implementing NewsDataSource and PriceDataSource interfaces
- **Basic Scheduler**: Simple polling loop (local execution)
- **Configuration**: API key management

#### Success Criteria
- ✅ Connects to Finnhub API successfully
- ✅ Fetches real financial data
- ✅ Stores data in SQLite locally
- ✅ Deduplication prevents reprocessing
- ✅ Can poll manually (no automation yet)

### File Structure (v0.21)
```
data/ (adds to v0.2)
├── config.py            # Dataclass with API keys, local env management
├── scheduler.py         # Simple polling coordinator (local only)
└── providers/
    ├── __init__.py      # Provider exports
    └── finnhub.py       # FinnhubNewsProvider(NewsDataSource) + FinnhubPriceProvider(PriceDataSource)
```

### Cost: $0 (Finnhub free tier)

---

## v0.22 - GitHub Actions Automation ☁️ **PHASE 3**

### Goal: Move to Cloud Execution

#### New Components
- **GitHub Actions Workflow**: 5-minute cron scheduling
- **Repository Storage**: SQLite committed back to repo
- **GitHub Secrets**: Secure API key management

#### Success Criteria
- ✅ GitHub Actions runs every 5 minutes
- ✅ Fetches data in cloud environment
- ✅ SQLite database persists across runs
- ✅ No local execution needed
- ✅ 24/7 automated operation

### File Structure (v0.22)
```
data/ (same as v0.21)
config.py            # Enhanced: GitHub Secrets integration

.github/workflows/
└── trading-bot.yml  # NEW: Every 5min polling + commit SQLite back to repo
```

### Cost: $0 (GitHub Actions free tier)

---

## v0.23 - Complete Basic System 🎯 **PHASE 4**

### Goal: Add Second Source + Filtering

#### New Components
- **RSS Provider**: Free news feeds backup
- **Keyword Filtering**: Urgent event detection
- **Enhanced Scheduler**: Coordinate multiple sources
- **Time Standardization**: UTC timestamps across all providers for reliable deduplication

#### Success Criteria
- ✅ Two data sources working (Finnhub + RSS)
- ✅ Keyword filtering detects urgent events
- ✅ Cross-source deduplication working
- ✅ Complete end-to-end system functional
- ✅ Ready for LLM integration (v0.3)

### File Structure (v0.23)
```
data/ (adds to v0.22)
├── filters.py           # NEW: Keyword matching: is_urgent(item), URGENT_KEYWORDS
├── scheduler.py         # Enhanced: poll multiple sources
└── providers/
    └── rss.py           # NEW: feedparser, publication date comparison
```

### Technical Flow (Complete)
```
Every 5min: scheduler → providers.fetch_incremental(last_seen_id) 
→ [Raw API Response → Provider converts to NewsItem/PriceData] 
→ deduplication.is_processed() → storage.store(standardized_models) 
→ filters.is_urgent() → [urgent: trigger LLM | normal: accumulate for 30min batch]

Every 30min: LLM agents process accumulated data → update analysis_results → 
[SUCCESS: delete processed raw data | FAILURE: preserve raw data for retry]
```

#### Provider Responsibility
Each provider (Finnhub, RSS, Reddit, etc.) is responsible for:
1. **API Communication**: HTTP requests, authentication, error handling
2. **Data Conversion**: Transform raw API responses into standardized `NewsItem`, `PriceData` models
3. **Time Standardization**: Convert all timestamps to UTC timezone-aware datetime objects
4. **Incremental Fetching**: Only request new data since last successful fetch

#### Provider Implementation Pattern
**Dual Providers** (for APIs providing both news and price data):
```python
# finnhub.py - Two classes sharing API key
class FinnhubNewsProvider(NewsDataSource):
    async def fetch_incremental() -> List[NewsItem]: ...

class FinnhubPriceProvider(PriceDataSource):  
    async def fetch_incremental() -> List[PriceData]: ...
```

**Single Providers** (for specialized APIs):
```python
# rss.py - News only
class RSSNewsProvider(NewsDataSource):
    async def fetch_incremental() -> List[NewsItem]: ...

# reddit.py - Social sentiment as news
class RedditSentimentProvider(NewsDataSource):
    async def fetch_incremental() -> List[NewsItem]: ...
```

**Benefits**: Type safety, single responsibility, shared configuration, independent polling schedules

### Cost: $0 (All free tiers)

---

## v0.25 - Complete Data Collection 📊 **EXPANSION MVP**

### Goal: Add Remaining Data Sources + Enhanced Features

#### Additional Data Sources (3 APIs)

##### Market Data & Backup
- **Polygon.io** (Enhanced Backup): Multi-ticker batching + advanced market data
  - Free: 5 calls/min (sufficient for 1 call per 5min polling)
  - Implementation: Batch API calls, timestamp-based incremental fetch

##### Sentiment & Regulatory Data  
- **Reddit API** (via PRAW): Social sentiment from retail traders
  - Free: 100 queries/min (non-commercial use)
  - Implementation: PRAW wrapper, subreddit monitoring, async coordination
- **SEC EDGAR**: Official company filings and insider trading
  - Free: 10 req/sec limit
  - Implementation: REST API, filing date filtering, XML/JSON parsing
  - Note: Stocks only, crypto doesn't have SEC filings

#### Enhanced Features
- **Advanced Filtering**: ML-ready keyword engine with configurable rules
- **Error Handling**: Circuit breakers, retry logic, graceful degradation
- **Performance Monitoring**: API response times, storage metrics, health checks
- **Data Quality**: Cross-source validation, freshness checks, anomaly detection

#### v0.25 Success Criteria
- ✅ All 5 data sources integrated and working
- ✅ Enhanced error handling and recovery
- ✅ Performance monitoring and alerting
- ✅ Data quality validation across sources
- ✅ Ready for LLM agent integration (v0.3+)

### Complete File Structure (v0.25)
```
data/
├── __init__.py          # Clean exports (DataSource, providers, scheduler)
├── base.py              # Abstract DataSource(ABC): fetch_incremental(), validate_connection()
├── models.py            # @dataclass NewsItem, PriceData, SentimentItem, FilingItem
├── config.py            # Dataclass with all API keys, GitHub Secrets integration
├── storage.py           # SQLite CRUD: store_items(), get_items_since(), schema setup  
├── deduplication.py     # Set-based tracking: is_processed(id), mark_processed(id)
├── filters.py           # Enhanced keyword matching + ML-ready architecture
├── scheduler.py         # Async coordinator: poll_all_sources(), error handling
├── health_monitor.py    # API health checks, performance metrics, alerting
└── providers/
    ├── __init__.py      # Provider exports
    ├── finnhub.py       # FinnhubNewsProvider + FinnhubPriceProvider (dual classes)
    ├── polygon.py       # PolygonNewsProvider + PolygonPriceProvider (dual classes)
    ├── rss.py           # RSSNewsProvider(NewsDataSource) - news only
    ├── reddit.py        # RedditSentimentProvider(NewsDataSource) - sentiment as news
    └── sec_edgar.py     # SECFilingsProvider(NewsDataSource) - regulatory news

.github/workflows/
└── trading-bot.yml      # GitHub Actions: every 5min polling + commit SQLite back to repo
```

### Cost Estimate for v0.25
- **Free Tier**: $0/month (all APIs within free limits)
- **Recommended**: $50/month (Finnhub paid tier for reliability)
- **Premium**: $150/month (Finnhub + Polygon.io paid tiers)

---

## v0.3+ - Trading Intelligence Layer 📋 **FUTURE PHASES**

### Multi-Agent Architecture
```
30-Min Raw Data Batches → Specialist LLM Agents → Persistent Analysis Results → Head Trader LLM → Trading Decisions
```

#### Agent Roles (Process 30-Minute Data Batches)
1. **News Analyst LLM**: Processes 30-min batches of Finnhub + RSS financial news
2. **Sentiment Analyst LLM**: Analyzes 30-min batches of Reddit social sentiment  
3. **SEC Filings Analyst LLM**: Reviews 30-min batches of EDGAR official company data
4. **Head Trader LLM**: Synthesizes all specialist analysis results + current holdings for final decision

#### Agent Processing Strategy
Each specialist LLM agent uses a **sort + rank** approach instead of numerical scoring:

**News Analyst LLM:**
- Input: 30-minute batch of NewsItem objects + previous analysis results
- Output: Updated analysis for each symbol (stored persistently)
  - **Bullish News**: Positive market impact items, ranked by importance
  - **Bearish News**: Negative market impact items, ranked by severity
- Updates: Previous analysis + new 30-min data → refreshed analysis per symbol

**Sentiment Analyst LLM:**
- Input: 30-minute batch of Reddit posts/comments + previous analysis results
- Output: Updated sentiment analysis for each symbol (stored persistently)
  - **Positive Sentiment**: Optimistic retail trader discussions, ranked by influence
  - **Negative Sentiment**: Pessimistic retail trader discussions, ranked by concern level
- Updates: Previous sentiment + new 30-min data → refreshed sentiment per symbol

**SEC Filings Analyst LLM:**
- Input: 30-minute batch of regulatory filings + previous analysis results
- Output: Updated regulatory analysis for each symbol (stored persistently)
  - **Positive Filings**: Beneficial regulatory news, ranked by impact
  - **Negative Filings**: Concerning regulatory news, ranked by risk level  
- Updates: Previous filings analysis + new 30-min data → refreshed regulatory view per symbol

**Head Trader LLM:**
- Input: All specialist analysis results (persistent) + current portfolio holdings
- Output: Final trading recommendations per symbol (stored persistently)
- Decision logic: Synthesizes all specialist views → HOLD/SELL recommendations with confidence levels

#### LLM Trigger Conditions
- **Urgent Events**: Immediate processing when keywords detected (processes raw data immediately)
- **Scheduled Analysis**: Every 30 minutes on accumulated 30-min batch
- **Data Cleanup**: After **successful** LLM analysis, raw data is deleted and analysis results are preserved
- **Error Handling**: If specialist LLMs or Head Trader fail to update analysis results, raw data is **preserved** for retry
- **Data Source**: LLMs process raw data batches, Head Trader reads persistent analysis results

### Core Trading Logic
- **Portfolio Management**: Current holdings tracking
- **Signal Generation**: Trading signals and recommendations
- **Decision Engine**: HOLD/SELL recommendation logic

### Orchestration & Infrastructure
- **Execution Environment**: GitHub Actions cloud runners (laptop can be off)
- **Data Polling**: Automated every 5 minutes during market hours
- **LLM Analysis**: Every 30 minutes + immediate urgent triggers
- **Storage**: SQLite database committed to GitHub repository
- **Persistence**: No local storage needed, fully cloud-based
- **Output Format**: Holdings analysis + summaries + recommendations

### Technical Implementation
- **File Structure**: Enterprise-grade Clean Architecture
- **Configuration**: Environment-based API key management
- **Performance Indexes**: Add SQLite indexes based on LLM query patterns (symbol+time, stance filtering)
- **Logging**: Structured logging for debugging and monitoring
- **Testing**: Integration tests for end-to-end workflows

---

## v1.0 - Complete Trading Bot 🎯 **FINAL TARGET**

### Full Feature Set
- ✅ **LLM Providers** (v0.1)
- 🔄 **Data Sources** (v0.2)  
- 📋 **Trading Agents** (v0.3+)
- 📋 **Orchestration** (v0.3+)
- 📋 **Scheduling** (v0.3+)
- 📋 **Production Infrastructure** (v1.0)

### Production Infrastructure Additions
- **Rate Limiting**: Per-provider API throttling to prevent bans
- **Advanced Filtering**: Replace keywords with lightweight local ML model
- **Data Validation**: Financial data accuracy and freshness checks
- **Error Handling**: Circuit breaker patterns and graceful degradation
- **Monitoring**: Comprehensive logging and health checks for both polling and LLM layers
- **Database Optimization**: Efficient storage and retrieval for high-frequency polling
- **Backup Systems**: Redundant data sources and failover mechanisms

### Success Metrics
- **Performance**: Beat buy-and-hold strategy
- **Reliability**: 99%+ uptime for data collection
- **Cost Efficiency**: Stay within $10-50/month budget
- **Risk Management**: Recommendations only, no actual trade execution

### Final Technical Stack
- **Python**: Financial libraries, all APIs have Python SDKs
- **GitHub Actions**: Free scheduling and execution
- **Clean Architecture**: Scalable, maintainable codebase
- **Async/Await**: High-performance concurrent API calls