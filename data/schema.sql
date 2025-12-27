-- Market Sentiment Analyzer SQLite schema
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- News items
CREATE TABLE IF NOT EXISTS news_items (
    url TEXT NOT NULL,
    headline TEXT NOT NULL,
    content TEXT,
    published_iso TEXT NOT NULL,
    source TEXT NOT NULL,
    news_type TEXT NOT NULL CHECK(news_type IN ('macro', 'company_specific')),
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (url)
) WITHOUT ROWID;

-- Symbol links
CREATE TABLE IF NOT EXISTS news_symbols (
    url TEXT NOT NULL,
    symbol TEXT NOT NULL,
    is_important INTEGER CHECK(is_important IN (0, 1)),
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (url, symbol),
    FOREIGN KEY (url) REFERENCES news_items(url) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS social_discussions (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    community TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    content TEXT,
    published_iso TEXT NOT NULL,
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (source, source_id)
) WITHOUT ROWID;

-- Price data
CREATE TABLE IF NOT EXISTS price_data (
    symbol TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,
    price TEXT NOT NULL CHECK(CAST(price AS REAL) > 0),
    volume INTEGER CHECK(volume >= 0),
    session TEXT DEFAULT 'REG' CHECK(session IN ('REG', 'PRE', 'POST', 'CLOSED')),
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, timestamp_iso)
) WITHOUT ROWID;

-- LLM analysis results
CREATE TABLE IF NOT EXISTS analysis_results (
    symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL CHECK(analysis_type IN ('news_analysis', 'sentiment_analysis', 'sec_filings', 'head_trader')),
    model_name TEXT NOT NULL,
    stance TEXT NOT NULL CHECK(stance IN ('BULL', 'BEAR', 'NEUTRAL')),
    confidence_score REAL NOT NULL CHECK(confidence_score BETWEEN 0 AND 1),
    last_updated_iso TEXT NOT NULL,
    result_json TEXT NOT NULL CHECK(json_valid(result_json) AND json_type(result_json) = 'object'),
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, analysis_type)
) WITHOUT ROWID;

-- Holdings
CREATE TABLE IF NOT EXISTS holdings (
    symbol TEXT NOT NULL,
    quantity TEXT NOT NULL CHECK(CAST(quantity AS REAL) > 0),
    break_even_price TEXT NOT NULL CHECK(CAST(break_even_price AS REAL) > 0),
    total_cost TEXT NOT NULL CHECK(CAST(total_cost AS REAL) > 0),
    notes TEXT,
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol)
) WITHOUT ROWID;

-- Provider cursor state
CREATE TABLE IF NOT EXISTS last_seen_state (
    provider TEXT NOT NULL CHECK(provider IN ('FINNHUB', 'POLYGON', 'REDDIT')),
    stream TEXT NOT NULL CHECK(stream IN ('COMPANY', 'MACRO', 'SOCIAL')),
    scope TEXT NOT NULL CHECK(scope IN ('GLOBAL', 'SYMBOL')),
    symbol TEXT NOT NULL DEFAULT '__GLOBAL__',
    timestamp TEXT,
    id INTEGER,
    CHECK ((timestamp IS NULL) != (id IS NULL)),
    PRIMARY KEY (provider, stream, scope, symbol)
);
