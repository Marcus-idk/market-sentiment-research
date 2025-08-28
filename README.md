# TradingBot

A lightweight US equities trading bot skeleton with strict data models, SQLite storage, and pluggable LLM providers (OpenAI, Gemini).

## Documentation Map
- Summary: High-level overview of goals, time policy (UTC vs ET), project structure, models, storage helpers, schema highlights, and tests.
  - `docs/Summary.md`
- Roadmap: Milestones and planned phases (v0.1–v1.0), components to add next, CI notes (WAL checkpoint), and testing overview.
  - `docs/roadmap.md`
- Configuration: Architecture for env-driven, per-provider settings and DI.
  - `docs/CONFIGURATION.md`
- Data Source APIs: Reference and plans for Finnhub, Polygon.io, RSS, Reddit, SEC EDGAR; rate limits, coverage, and implementation notes.
  - `data/API_Reference.md`
- LLM Providers Guide: How to use `OpenAIProvider` and `GeminiProvider` with parameters, examples, and tips for tools/reasoning/structured output.
  - `llm/llm-providers-guide.md`

