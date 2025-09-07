# Data Source APIs Reference

## Overview
This document outlines the 5 data sources planned for US equities (stocks). Cryptocurrency is out of scope for the current milestone and may be considered later.

---

## 1. Finnhub API 📈
**Primary financial data source**

### What it provides:
- Real-time stock prices and crypto prices
- Company financial news
- Market data (volume, OHLC)
- Company profiles and metrics

### Rate Limits:
- Vary by plan; free tier is typically ~60 calls/minute. Confirm current plan-specific limits in your Finnhub dashboard.
- Paid tiers increase limits (e.g., 300+/min), subject to change.

### Data Coverage:
- ✅ Stocks (US markets)
- ✅ Financial news
- ✅ Market data

### Implementation:
- REST API with JSON responses
- Incremental fetch via timestamp filtering
- Primary source for v0.2.1

### Endpoints Used in v0.2.1 (Concise)
- Company News (per symbol):
  - Method/Path: `GET /company-news`
  - Params: `symbol` (ticker), `from` (YYYY-MM-DD), `to` (YYYY-MM-DD), `token` (API key)
  - Returns: array of objects with fields including `datetime` (epoch seconds, UTC), `headline`, `source`, `summary`, `url`, `id`, `category`, `image`, `related`.
  - Notes: We map `headline`, `url`, `source`, `datetime→published`, `summary→content`; `symbol` comes from the request symbol. Finnhub docs don’t explicitly state whether `to` is inclusive; we treat it as inclusive and still filter client‑side to `published > since` to avoid duplicates.
- Quote (per symbol):
  - Method/Path: `GET /quote`
  - Params: `symbol` (ticker), `token` (API key)
  - Returns: object with keys `c` (current price), `h` (high), `l` (low), `o` (open), `pc` (prev close), `t` (epoch seconds), and often `d`, `dp`.
  - Notes: We map `c→price` (must be > 0), `t→timestamp` (fallback to now if 0 — defensive), `volume=None`, `session=REG`.

---

## 2. Polygon.io API 📊
**Enhanced market data backup**

### What it provides:
- Advanced market data (OHLC, volume)
- Real-time and historical prices
- Multi-ticker batch requests
- Market status and holidays

### Rate Limits:
- **Free tier**: 5 calls/minute
- **Paid tier**: 100+ calls/minute ($99/month)

### Data Coverage:
- ✅ Stocks (US markets)
- ❌ News content
- ✅ Advanced market metrics

### Implementation:
- REST API with efficient batch calls
- 1 call per 5-minute polling = well within limits
- Backup/redundancy for Finnhub

---

## 3. RSS Feeds 📰
**Free news aggregation**

### What it provides:
- Financial news from multiple sources
- Company-specific news feeds
- Market analysis articles
- Economic reports

### Rate Limits:
- **No limits** (standard RSS)
- Self-throttle to be respectful

### Data Coverage:
- ✅ Stocks (company news)
- ✅ Economic indicators
- ✅ Market analysis

### Implementation:
- feedparser library
- Publication date comparison for incremental fetch
- Free backup news source

---

## 4. Reddit API (PRAW) 💬
**Social sentiment analysis**

### What it provides:
- Retail trader discussions
- Social sentiment indicators
- Community reactions to news
- Trending ticker mentions

### Rate Limits:
- **Free tier**: 100 queries/minute (non-commercial)
- **OAuth required** for sustained access

### Data Coverage:
- ✅ Stocks (r/stocks, r/investing)
- ✅ Social sentiment
- ✅ Retail trader behavior

### Implementation:
- PRAW wrapper library
- Subreddit monitoring
- Async coordination with other sources

---

## 5. SEC EDGAR API 🏛️
**Official regulatory filings**

### What it provides:
- Company financial statements
- Insider trading reports
- Official SEC filings (10-K, 10-Q, 8-K)
- Executive compensation data

### Rate Limits:
- **Free tier**: 10 requests/second
- **No daily limits** with proper headers

### Data Coverage:
- ✅ Stocks (US public companies only)
- ❌ Cryptocurrency (no SEC filings)
- ✅ Official financial data
- ✅ Regulatory events

### Implementation:
- REST API with XML/JSON responses
- Filing date filtering for incremental fetch
- Stocks-only data source

---

## Usage Strategy

### Polling Schedule (Every 5 Minutes)
```
Finnhub: 1 call/5min = 12 calls/hour (well within 60/min limit)
Polygon: 1 call/5min = 12 calls/hour (well within 5/min limit)
RSS: 1-3 feeds/5min = minimal load
Reddit: 1-2 queries/5min = minimal load  
SEC EDGAR: 1 call/5min = 12 calls/hour (well within limits)
```

### Cost Structure
- **v0.2.1**: $0/month (Finnhub free only)
- **v0.2.3**: $0/month (All free tiers)
- **v0.2.4**: $0-50/month (Optional paid tiers for reliability)

### Data Flow
```
API → Raw Data → models.py (NewsItem/PriceData) → storage.py (SQLite) → LLM Agents
```

---

## Implementation Phases

### v0.2.1: Finnhub Only
- Single API integration
- Local polling and storage
- Foundation testing

### v0.2.3: + RSS Feeds  
- Two data sources
- Cross-source deduplication
- Basic filtering system

### v0.2.4: All 5 APIs
- Complete data collection (US equities)
- Enhanced error handling
- Production-ready system
