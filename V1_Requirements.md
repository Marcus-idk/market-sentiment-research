# Trading Bot Development Plan

## Project Goal
Build an automated trading bot that leverages LLMs for fundamental analysis to gain an edge over retail traders. The bot will poll data sources every 5 minutes, filter for urgent events, and provide hold/sell recommendations via scheduled LLM analysis.

## Core Strategy
- **Target Competition**: Retail traders (not institutional HFT firms)
- **Edge**: LLM analyzing hundreds of sources 24/7 vs manual traders reading 2-3 sources
- **Final Scope**: Monitor existing positions only (no new trade discovery)

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

## v0.2 - Core Infrastructure Foundation 🏗️ **PHASE 1**

### Goal: Build Solid Foundation Without APIs

#### Core Components
- **Data Models**: NewsItem, PriceData DTOs with validation
- **Storage Layer**: SQLite schema, CRUD operations
- **Abstract Interface**: Type-safe DataSource classes (NewsDataSource, PriceDataSource)
- **Local Testing**: Test with mock/hardcoded data

#### Success Criteria
- ✅ SQLite database creates tables correctly
- ✅ Data models serialize/deserialize properly
- ✅ Storage operations work (insert, retrieve, update)
- ✅ Abstract DataSource interface defined
- ✅ Basic deduplication logic functional

### File Structure (v0.2)
```
data/
├── __init__.py          # Clean exports
├── base.py              # Abstract DataSource classes: NewsDataSource→List[NewsItem], PriceDataSource→List[PriceData]
├── models.py            # @dataclass NewsItem, PriceData with validation
├── storage.py           # SQLite CRUD: store_items(), get_items_since(), schema setup
├── deduplication.py     # Set-based tracking: is_processed(id), mark_processed(id)
└── providers/
    └── __init__.py      # Provider exports (empty for now)
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
→ filters.is_urgent() → [urgent: trigger LLM | normal: store for 30min batch]
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
Stored Data → Specialized LLM Agents → Final Decision Agent → User
```

#### Agent Roles (Process Stored Data Only)
1. **News Analyst LLM**: Processes stored Finnhub + RSS financial news
2. **Sentiment Analyst LLM**: Analyzes stored Reddit social sentiment  
3. **SEC Filings Analyst LLM**: Reviews stored EDGAR official company data
4. **Head Trader LLM**: Synthesizes all filtered data + current holdings for final decision

#### Agent Processing Strategy
Each specialist LLM agent uses a **sort + rank** approach instead of numerical scoring:

**News Analyst LLM:**
- Input: Batch of stored NewsItem objects from Finnhub + RSS
- Output: Two ranked lists
  - **Bullish News**: Positive market impact items, ranked by importance
  - **Bearish News**: Negative market impact items, ranked by severity
- Ranking criteria: Market relevance, company impact, timing sensitivity

**Sentiment Analyst LLM:**
- Input: Batch of stored Reddit posts/comments
- Output: Two ranked lists  
  - **Positive Sentiment**: Optimistic retail trader discussions, ranked by influence
  - **Negative Sentiment**: Pessimistic retail trader discussions, ranked by concern level
- Ranking criteria: Discussion volume, credibility indicators, emotional intensity

**SEC Filings Analyst LLM:**
- Input: Batch of stored regulatory filings
- Output: Two ranked lists
  - **Positive Filings**: Beneficial regulatory news, ranked by impact
  - **Negative Filings**: Concerning regulatory news, ranked by risk level  
- Ranking criteria: Legal significance, financial impact, compliance implications

**Head Trader LLM:**
- Input: All ranked lists from specialist agents + current portfolio holdings
- Output: Final trading recommendations (HOLD/SELL) with confidence levels
- Decision logic: Weighs bullish vs bearish signals, considers position sizing and risk

#### LLM Trigger Conditions
- **Urgent Events**: Immediate processing when keywords detected
- **Scheduled Analysis**: Every 30 minutes on accumulated filtered dataset
- **Data Source**: Always from local storage, never direct API calls

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