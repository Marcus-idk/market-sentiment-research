# Configuration Architecture

---

## Goals
- Simple now (v0.2.1); scales to 5+ sources and multiple LLMs.
- No globals; no import‑time env reads; testable and CI‑friendly.

---

## Design Principles
- 12‑Factor: secrets via env vars (e.g., `FINNHUB_API_KEY`, `OPENAI_API_KEY`).
- Dependency Injection: providers accept settings objects; never read env directly.
- Import boundaries: config modules use stdlib only. An optional loader may use `python‑dotenv`; if missing, it no‑ops. Data/LLM never import config.
- Entry points (CLI/tests/GHA) load env and construct settings.

---

## Layout (current)
```
config/
├── __init__.py
├── providers/
│   ├── __init__.py
│   └── finnhub.py           # FinnhubSettings
└── llm/
    └── __init__.py          # (future provider settings live here)
```

---

## Minimal Usage
- Finnhub settings (typed, frozen):
```python
# config/providers/finnhub.py
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class FinnhubSettings:
    api_key: str
    base_url: str = "https://finnhub.io/api/v1"
    rate_limit_per_min: int = 60

    @staticmethod
    def from_env(env=os.environ):
        key = env.get("FINNHUB_API_KEY")
        if not key:
            raise ValueError("FINNHUB_API_KEY is required")
        return FinnhubSettings(api_key=key)
```
- Environment loading: call `load_dotenv()` once in the entry point (CLI/tests/GHA). No wrapper function is needed.

---

## CI / GitHub Actions
- Store secrets in repo settings; the workflow injects env vars.
- No `.env` in CI; local runs may use `python‑dotenv` at the CLI/runner layer.

---

## Testing
- Construct settings directly in unit tests (no globals).
- For integration tests, pass settings created from a test env mapping.

---

## Status
- Applies starting with v0.2.1. Add new providers by dropping a dataclass in `config/providers/` (or `config/llm/`) with a `from_env` constructor. There is no `config/core.py` at this stage.

