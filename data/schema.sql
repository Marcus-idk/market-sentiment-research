-- Trading Bot SQLite Schema
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- Raw data: News (normalized URLs for dedup; UTC ISO timestamps)
CREATE TABLE IF NOT EXISTS news_items (
    symbol TEXT NOT NULL,
    url TEXT NOT NULL,                  -- normalized (tracking params stripped)
    headline TEXT NOT NULL,
    content TEXT,
    published_iso TEXT NOT NULL,        -- UTC ISO "YYYY-MM-DDTHH:MM:SSZ"
    source TEXT NOT NULL,               -- finnhub, polygon, rss, etc.
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, url)
) WITHOUT ROWID;

-- Raw data: Prices (Decimal as TEXT; UTC ISO timestamps; session enum)
CREATE TABLE IF NOT EXISTS price_data (
    symbol TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,        -- UTC ISO
    price TEXT NOT NULL CHECK(CAST(price AS REAL) > 0), -- Decimal as TEXT
    volume INTEGER CHECK(volume >= 0),
    session TEXT DEFAULT 'REG' CHECK(session IN ('REG', 'PRE', 'POST', 'CLOSED')),
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, timestamp_iso)
) WITHOUT ROWID;

-- Persistent: LLM analysis results (one per symbol/type; JSON object)
CREATE TABLE IF NOT EXISTS analysis_results (
    symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL CHECK(analysis_type IN ('news_analysis', 'sentiment_analysis', 'sec_filings', 'head_trader')),
    model_name TEXT NOT NULL,
    stance TEXT NOT NULL CHECK(stance IN ('BULL', 'BEAR', 'NEUTRAL')),
    confidence_score REAL NOT NULL CHECK(confidence_score BETWEEN 0 AND 1),
    last_updated_iso TEXT NOT NULL,     -- UTC ISO
    result_json TEXT NOT NULL CHECK(json_valid(result_json) AND json_type(result_json) = 'object'),
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol, analysis_type)
) WITHOUT ROWID;

-- Persistent: Holdings
CREATE TABLE IF NOT EXISTS holdings (
    symbol TEXT NOT NULL,
    quantity TEXT NOT NULL CHECK(CAST(quantity AS REAL) > 0),       -- Decimal as TEXT
    break_even_price TEXT NOT NULL CHECK(CAST(break_even_price AS REAL) > 0),
    total_cost TEXT NOT NULL CHECK(CAST(total_cost AS REAL) > 0),
    notes TEXT,
    created_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at_iso TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (symbol)
) WITHOUT ROWID;

-- State: incremental fetch and LLM cutoff
CREATE TABLE IF NOT EXISTS last_seen (
    key TEXT PRIMARY KEY CHECK(key IN ('news_since_iso', 'llm_last_run_iso')),
    value TEXT NOT NULL
) WITHOUT ROWID;
