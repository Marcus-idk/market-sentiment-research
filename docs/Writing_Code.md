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
- Imports: absolute project imports. Default to folder‑level (`from data.storage import …`); use submodules only when needed. Prefer top‑of‑file imports; use function‑level imports only for optional dependencies or to avoid cycles (and document why). Facades (e.g., `data/storage/__init__.py`) keep `from data.storage` stable.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Time and numbers: use timezone‑aware timestamps (UTC recommended); use precise numeric types for money (avoid binary floats).
- Datetime flow: API/raw input → model constructors (normalize to UTC) → storage helpers (`_datetime_to_iso`) → SQLite ISO strings ending with `Z`; read paths reverse this. Never format timestamps by hand. Use `data.models._normalize_to_utc(dt)` inside models for consistency.
- Market sessions: Use `utils.market_sessions.classify_us_session()` for session classification (PRE/REG/POST/CLOSED). Handles NYSE holidays/early closes and UTC→ET conversion.
- Persistence: validate at write boundaries; choose stable representations; version schema/migrations clearly.
- SQLite access: use `data.storage._cursor_context(db_path, commit=True|False)` for all read/write operations. It ensures foreign keys, row factory, commit/rollback, and cleanup. Avoid direct `connect()` except for:
  - `init_database()` / `finalize_database()` lifecycle calls, or
  - Highly specific PRAGMA sequences that require connection-level access (e.g., WAL checkpointing in maintenance code or tests).
  Prefer cursor-level helpers in application code; keep any direct connection usage contained and documented.
- Logging: structured and actionable; no secrets/API keys; appropriate levels.
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
