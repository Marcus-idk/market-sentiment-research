# Data_API_Reference

## What this file is
A **contract-only reference** for external data providers we call. It explains **what data** we use them for and **how to call** them (auth, base URLs, routes, params) with brief response semantics. Implementation details live elsewhere.

## Symbol Guide
For each provider's **"What they provide"** section:
- **List items** = data domains AVAILABLE from that provider's API
- **✅** = Available AND currently USED/IMPLEMENTED in our project
- **❌** = Available from the API but NOT USED YET in our project
- **Not listed** = Not available from that provider at all

The **"Endpoints"** section shows only what we actually call/use (matching the ✅ items above).

## Data domains we ingest
- **Macro News** — Major market-moving events.
- **Company News** — News about specific companies.
- **People News** — News about key people (executives, insiders).
- **Filings** — Official company filings and disclosures.
- **Social/Sentiment** — Online crowd sentiment.
- **Prices/Market Data** — Stock prices and trading data.

---

## Provider: Finnhub
**Auth & Base**: API key (query/header) · Base: `https://finnhub.io/api/v1`

**What they provide**
- Macro News — ✅
- Company News — ✅
- Prices/Market Data — ✅

**Endpoints**
- Macro News — `GET /news`
  - Params: `category` (`general` | `forex` | `crypto` | `merger`), `minId` (optional), `token`
  - Returns:
    ```json
    [
      {
        "category": "general",
        "datetime": 1727865600,
        "headline": "Stocks rise as investors digest inflation data",
        "id": 123456789,
        "image": "https://example.com/image.jpg",
        "related": "",
        "source": "Reuters",
        "summary": "U.S. stocks climbed after new CPI figures...",
        "url": "https://www.reuters.com/markets/us/..."
      }
    ]
    ```

- Company News — `GET /company-news`
  - Params: `symbol`, `from` (`YYYY-MM-DD`), `to` (`YYYY-MM-DD`), `token`
  - Returns:
    ```json
    [
      {
        "category": "company",
        "datetime": 1696012800,
        "headline": "Apple launches new product line",
        "id": 987654321,
        "image": "https://example.com/aapl.jpg",
        "related": "AAPL",
        "source": "Reuters",
        "summary": "Apple unveiled its latest devices at an event...",
        "url": "https://www.reuters.com/technology/..."
      }
    ]
    ```

- Prices/Market Data — `GET /quote`
  - Params: `symbol`, `token`
  - Returns:
    ```json
    {
      "c": 261.74,
      "h": 263.31,
      "l": 260.68,
      "o": 261.07,
      "pc": 259.45,
      "t": 1582641000
    }
    ```

---

## Provider: Polygon.io
**Auth & Base**: API key (query param `apiKey`) · Base: `https://api.polygon.io`

**What they provide**
- Prices/Market Data — ✅

**Endpoints**
- Prices/Market Data — `GET /v2/snapshot/locale/us/markets/stocks/tickers/{symbol}`
  - Path: `symbol` (ticker, case-sensitive)
  - Params: `apiKey`
  - Returns:
    ```json
    {
      "status": "OK",
      "ticker": {
        "ticker": "AAPL",
        "updated": 1699891198523000000,
        "lastTrade": {
          "p": 150.26,
          "s": 100,
          "t": 1699891198523000000,
          "x": 4
        },
        "lastQuote": {
          "P": 150.27,
          "p": 150.25,
          "S": 10,
          "s": 5,
          "t": 1699891198507251700
        },
        "day": {
          "c": 150.26,
          "h": 151.20,
          "l": 149.50,
          "o": 150.00,
          "v": 28727868,
          "vw": 150.12
        }
      }
    }
    ```
  - **Note**: Timestamps are in nanoseconds. We prefer `lastTrade.p` (actual execution) over quote midpoint.

- Connection Validation — `GET /v1/marketstatus/now`
  - Params: `apiKey`
  - Used for validating API connectivity (cheap endpoint, doesn't count against rate limits)

**Rate Limits**
- Free tier: ~5 calls/min
- Caution: Fetching per-symbol snapshots with large watchlists may exceed free tier limits (e.g., >25 symbols with 5-min polling)

---

## Notes
- Keep this file concise and **contract-only**.
