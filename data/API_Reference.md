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
- **Free tier**: 60 calls/minute
- **Paid tier**: 300+ calls/minute ($25/month)

### Data Coverage:
- ✅ Stocks (US markets)
- ✅ Financial news
- ✅ Market data

### Implementation:
- REST API with JSON responses
- Incremental fetch via timestamp filtering
- Primary source for v0.2.1

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
- **v0.23**: $0/month (All free tiers)
- **v0.25**: $0-50/month (Optional paid tiers for reliability)

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

### v0.23: + RSS Feeds  
- Two data sources
- Cross-source deduplication
- Basic filtering system

### v0.25: All 5 APIs
- Complete data collection (US equities)
- Enhanced error handling
- Production-ready system
