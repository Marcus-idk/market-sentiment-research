-- SQLite Database Schema for Trading Bot v0.2
-- Architecture: Temporary raw data + Persistent LLM analysis results

-- Critical settings to prevent failures
PRAGMA journal_mode = WAL;        -- Allows reading while writing (no "database locked" errors)
PRAGMA synchronous = NORMAL;      -- Fast writes for GitHub Actions (vs painfully slow default)

-- ===============================
-- RAW DATA TABLES (TEMPORARY)
-- ===============================
-- These tables store 30-minute batches of data
-- DELETED after successful LLM processing
-- PRESERVED if any LLM fails (for retry)

-- News Items (30-minute staging)
-- IMPORTANT: URLs must be normalized before storage to enable cross-provider deduplication
-- Strip tracking parameters: ?utm_source=, ?ref=, ?fbclid=, etc.
-- Example: "https://reuters.com/article/123?utm_source=finnhub" → "https://reuters.com/article/123"
CREATE TABLE news_items (
    symbol TEXT NOT NULL,
    url TEXT NOT NULL,                  -- NORMALIZED URL (tracking params stripped)
    headline TEXT NOT NULL,
    content TEXT,                       -- Full article body (short retention)
    published_iso TEXT NOT NULL,        -- ISO format: "2024-01-15T10:30:00Z"
    source TEXT NOT NULL,               -- finnhub, polygon, rss, etc.
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, url)
) WITHOUT ROWID;

-- Price Data (30-minute staging)
CREATE TABLE price_data (
    symbol TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,        -- When the bar closed (UTC): "2024-01-15T10:30:00Z"
    price TEXT NOT NULL CHECK(CAST(price AS REAL) > 0), -- Close price (exact decimal as string)
    volume INTEGER CHECK(volume >= 0),  -- Traded amount (whole shares for stocks)
    session TEXT DEFAULT 'REG' CHECK(session IN ('REG', 'PRE', 'POST')),  -- REG=regular, PRE=pre-market, POST=post-market
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, timestamp_iso)
) WITHOUT ROWID;

-- ===============================
-- ANALYSIS RESULTS (PERSISTENT)
-- ===============================
-- LLM analysis results - NEVER deleted, only updated
-- Each specialist LLM has one current view per symbol

CREATE TABLE analysis_results (
    symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL CHECK(analysis_type IN ('news_analysis', 'sentiment_analysis', 'sec_filings', 'head_trader')),
    model_name TEXT NOT NULL,           -- "gpt-5", "gemini-2.5-flash"
    stance TEXT NOT NULL CHECK(stance IN ('BULL', 'BEAR', 'NEUTRAL')),
    confidence_score REAL NOT NULL CHECK(confidence_score BETWEEN 0 AND 1), -- 0.0 to 1.0
    last_updated_iso TEXT NOT NULL,     -- ISO format: "2024-01-15T10:30:00Z"
    result_json TEXT NOT NULL CHECK(json_valid(result_json) AND json_type(result_json) = 'object'), -- LLM analysis in JSON format
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, analysis_type)
) WITHOUT ROWID;

-- ===============================
-- HOLDINGS (PERSISTENT)
-- ===============================
-- Portfolio tracking with break-even calculations

CREATE TABLE holdings (
    symbol TEXT NOT NULL,
    quantity TEXT NOT NULL CHECK(CAST(quantity AS REAL) > 0), -- Position size (exact decimal as string)
    break_even_price TEXT NOT NULL CHECK(CAST(break_even_price AS REAL) > 0), -- Break even price (exact decimal as string)
    total_cost TEXT NOT NULL CHECK(CAST(total_cost AS REAL) > 0), -- Total cost basis (exact decimal as string)
    notes TEXT,                         -- Optional notes about position
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol)
) WITHOUT ROWID;

-- ===============================
-- PERFORMANCE INDEXES
-- ===============================
-- Indexes will be added later when implementing LLM query patterns