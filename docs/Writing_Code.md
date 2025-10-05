# Writing Code Guidelines

Purpose: Keep code simple, correct, and consistent with the codebase.

Scope: Applies to all new/changed code. New code should follow existing patterns first; propose improvements when they clearly reduce complexity or risk.

## SWE Best Practices (Must)
- Prefer simple solutions (KISS). One clear responsibility per module/function.
- Avoid duplication (DRY) when the abstraction is real; avoid premature abstraction.
- Validate inputs at boundaries; fail fast on invalid state; make types explicit (use dataclasses/enums where helpful).
- Handle errors explicitly; raise domain‑specific exceptions; do not swallow errors.
- Centralize cross‑cutting concerns (I/O, HTTP, retries/backoff, time zones, data normalization, logging). Reuse helpers.

## Long‑Term Design (Must Think)
- Ask: Will this be reused soon? If yes, follow existing interfaces. If no, keep it local and simple.
- Keep boundaries clean: configuration → adapters/clients → models/storage → services/workflows; avoid circular dependencies.
- Add extension points only when there are at least two real uses.
- Use async for I/O; never block inside async paths; reuse retry/HTTP utilities.

## Consistency (Must)
- Mirror existing file layout, naming, and style. New code follows old code.
- Imports: absolute project imports. Default to package facades (`from data.storage import …`, `from data.providers.finnhub import …`); use submodules only when needed. Prefer top-of-file imports; use function-level imports only for optional dependencies or to avoid cycles (and document why). Facades (e.g., `data/storage/__init__.py`, `data/providers/finnhub/__init__.py`) keep canonical imports stable.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Type annotations (Python 3.10+): use built-in generics and unions — for example `list[str]`, `dict[str, Any]`, `tuple[int, ...]`, and `X | None` instead of `typing.List`, `typing.Dict`, `typing.Tuple`, `typing.Optional`, or `typing.Union`. Preserve type parameters when converting. Keep `typing.Mapping`, `Any`, `Callable`, `Awaitable`, `Iterator`, and `TypeVar` where needed.
- Keyword-only arguments: Use `*` to enforce keyword-only params when:
  - Function has 4+ optional parameters (easy to mix up order)
  - Multiple similar types (e.g., `timeout, max_retries, base, mult` - all numbers)
  - Boolean flags benefit from named clarity (`validate=True` clearer than `True`)
  - Base classes with multiple cursors/strategies (e.g., `since` vs `min_id`)
  - Examples: `get_json_with_retry(url, *, timeout, max_retries, base, mult, jitter)`, `fetch_incremental(self, *, since=None, min_id=None)`, `parse_symbols(raw, filter_to, *, validate=True, log_label="SYMBOLS")`
  - Don't use for simple 1-3 param functions, obvious param order, or dataclasses (convention: positional-or-keyword)
  - Rule of thumb: if caller would benefit from seeing parameter names, use `*`
- Time and numbers: use timezone‑aware timestamps (UTC recommended); use precise numeric types for money (avoid binary floats).
- Datetime flow: API/raw input → model constructors (normalize to UTC) → storage helpers (`_datetime_to_iso`) → SQLite ISO strings ending with `Z`; read paths reverse this. Never format timestamps by hand. Use `data.models._normalize_to_utc(dt)` inside models for consistency.
- Market sessions: Use `utils.market_sessions.classify_us_session()` for session classification (PRE/REG/POST/CLOSED). Handles NYSE holidays/early closes and UTC→ET conversion.
- Persistence: validate at write boundaries; choose stable representations; version schema/migrations clearly.
- SQLite access: use `data.storage._cursor_context(db_path, commit=True|False)` for all read/write operations. It ensures foreign keys, row factory, commit/rollback, and cleanup. Avoid direct `connect()` except for:
  - `init_database()` / `finalize_database()` lifecycle calls, or
  - Highly specific PRAGMA sequences that require connection-level access (e.g., WAL checkpointing in maintenance code or tests).
  Prefer cursor-level helpers in application code; keep any direct connection usage contained and documented.
- Logging: structured and actionable; no secrets/API keys; appropriate levels. Use layered logging:
  - **Provider layer**: Module-level logger (`logger = logging.getLogger(__name__)`). Use `debug` for per-item drops (e.g., invalid article, malformed quote), `warning` for per-symbol/request failures (e.g., entire symbol fetch failed). Let genuine exceptions propagate to orchestrators.
  - **Orchestrator layer** (e.g., poller, workflows): Log high-level summaries at `info` (successful operations, counts), `warning` (partial failures), and `error` (critical workflow failures). Avoid duplicate logging—if a provider already logged debug details, the orchestrator should only summarize.
  - This split keeps modules cohesive: providers stay responsible for translating API responses, orchestrators stay responsible for workflow health. Operators get actionable telemetry without flooding logs.
  - **Formatting**: Use f-strings for all log messages (e.g., `logger.info(f"Stored {count} items")`). Consistent with codebase style, readable, and performance difference is negligible for logging.
  - **Exception logging**: In exception handlers, use `logger.exception(...)` instead of `logger.error(..., exc_info=True)`. It's clearer, shorter, and automatically includes stack traces.
  - **When to log what** (level guide):
    - `debug`: Invalid/filtered input (expected), skipped items with context (e.g., `Skipping article for AAPL: missing headline`)
    - `warning`: Partial provider failures, degraded fallbacks (e.g., `Finnhub quote missing field 'c' for AAPL`, `Using now() for invalid timestamp`)
    - `error`: Full request failures, provider outages (may retry)
    - `exception`: Unexpected exceptions (bugs) - use in `except` blocks for automatic stack traces
- Comments/docstrings: brief and explain "why", not just "what".

## Tests & Docs (Must)
- Add/adjust tests for every change. Follow the project’s testing conventions; mark slower integration/network tests.
- Update summary/architecture docs when public APIs, schemas, or test structure change. Keep README links valid.
- Prefer small, focused tests and minimal examples with clear names.

## Code Review Quick Checklist
- Correctness: timezones/units precise; money uses precise types; error paths covered; retries/backoff where needed.
- Consistency: matches surrounding style, import order, naming.
- Design: right abstraction level; clear boundaries; no premature generalization.
- Security/Perf: no secrets in code/logs; validate inputs; batch external calls; respect rate limits/timeouts; avoid unnecessary allocations.
