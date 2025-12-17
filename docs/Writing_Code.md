# Writing Code Guidelines

## 📝 HOW TO EXTEND THIS DOCUMENT
- Add rules under appropriate section (MUST/SHOULD)
- Format: `### RULE_NAME` → description → example
- Keep examples minimal but demonstrative
- Test that examples work before adding

---

## PROJECT CONTEXT
- **Python Version**: 3.13.x (requires 3.13+)
- **Principle**: Follow existing patterns. Propose improvements only when they clearly reduce complexity.
- **Scope**: All new/changed code

---

# MUST-FOLLOW RULES

### FILE_SIZE_LIMITS
- Max file size: 600 lines (target: ~400)
- Max test class size: ~200–250 lines

### PYTHON_VERSION
Use Python 3.13+ modern syntax.
```python
# ✅ list[str], dict[str, int | None], match statements, built-in generics
# ❌ typing.List, typing.Optional, typing.Union
```

### SIMPLICITY_KISS
One clear responsibility per module/function.
```python
# ✅ calculate_session(timestamp) - single purpose
# ❌ process_and_store_and_notify_and_log(data) - too many responsibilities
```

### FOLLOW_SIMILAR_CODE
When implementing similar functionality, find and study the existing implementation. Follow its structure, patterns, and conventions—including variable naming, comments, and code style—but don't blindly copy code that doesn't apply to your use case.

### DRY_PRINCIPLE
Avoid duplication when abstraction is real. Avoid premature abstraction.

### NO_DEAD_CODE
Remove unused variables, imports, and functions. Implementations should only
declare the cursor parameters they actually support, and orchestrators must
invoke providers with the matching keyword arguments.

### LINTER_SUPPRESSION
Use `# noqa` comments sparingly and only when the linter is wrong. Always specify the rule code.
```python
# ✅ GOOD: Intentional unused import with reason
from datetime import timezone  # noqa: F401 - used by tests via monkeypatch

# ✅ GOOD: Long line that can't be broken
URL = "https://example.com/very/long/path/that/cannot/be/split"  # noqa: E501

# ❌ BAD: Suppressing without reason
from json import loads  # noqa

# ❌ BAD: Suppressing all rules
result = complex_function()  # noqa

# Default: Fix the code instead of suppressing warnings
```

Defensive checks for external contracts must log a warning or raise when triggered; otherwise remove them.

```python
# ✅ GOOD: Assert external API contract with visible signal
if buffer_time and published <= buffer_time:
    logger.warning(
        "Provider returned item at/before cutoff %s (filter gt %s)", published, buffer_time
    )
    return None

# ❌ BAD: Silent redundant check (hidden anomaly)
if buffer_time and published <= buffer_time:
    return None
```

### VALIDATE_INPUTS
Validate at boundaries, fail fast on invalid state, make types explicit.
```python
def store_price(symbol: str, price: Decimal) -> None:
    if price <= 0:
        raise ValueError(f"Invalid price {price} for {symbol}")
    # Use dataclasses/enums where helpful; use frozen=True for config/settings that must not change
```

### ERROR_HANDLING
- Fail fast on structural/contract errors at boundaries by raising domain-specific exceptions (e.g., `DataSourceError`, `LLMError`); do not silently continue.
- For external APIs, treat authentication/4xx as non-retryable data errors and 408/429/5xx as retryable; propagate these as `DataSourceError` or `RetryableError`, never swallow them.
- Orchestrators may catch domain errors and a small, explicit set of runtime/OS errors to log and continue; truly unexpected exceptions should usually bubble to the top-level entrypoint rather than being hidden.

### ERROR_HANDLING_EXPECTED_PARSING
- Parsing helpers may return sentinel values (like `None`) without logging only when this behavior is part of the function contract and clearly documented.
- Use this for “expected fallthrough” cases, not for malformed or contract-breaking input.

### CLEANUP_SHUTDOWN
- Broad catches (`except Exception` or `except BaseException`) are allowed only in shutdown/cleanup code (e.g., UI/process teardown, DB rollback) or health-check probes.
- In cleanup, log the failure and then either re-raise (for transactional helpers) or continue shutdown; never hide that cleanup failed.

### PER_ITEM_CATCHES
- In per-item parsing loops, catch only explicit data issues (`ValueError`, `TypeError`, `KeyError`, `AttributeError`, and provider-domain errors) and skip bad items with DEBUG logs.
- Do not use `except Exception` inside per-item loops; malformed items should not crash the batch, but unexpected errors should still surface.

### CAUSE_CHAINING
- When wrapping exceptions, use `raise ... from exc` so upstream callers retain the original traceback.

### CENTRALIZE_CONCERNS
Centralize I/O, HTTP, retries/backoff, timezones, data normalization, logging.
**ALWAYS check `utils/` and `data/storage/storage_utils.py` for existing helpers before writing new code.**

Timestamp parsing: prefer shared helpers for RFC3339/ISO conversions; don’t duplicate parsing across providers.

```python
# ✅ GOOD: Centralize parsing
from utils.datetime_utils import parse_rfc3339
from data.storage.storage_utils import _datetime_to_iso
published = parse_rfc3339(ts_str)
published_iso = _datetime_to_iso(published)

# ❌ BAD: Repeating multi-branch parsing logic inline in providers
```

### EXTENSION_POINTS
Add only when 2+ real uses exist.
```python
# ✅ Add interface when FinnhubProvider AND AlphaVantageProvider need it
# ❌ Don't add "just in case"
```

Provider parameters and configurability: avoid premature config; use internal constants unless there’s demonstrated need.

```python
# ✅ Internal constants within provider package
NEWS_LIMIT = 100  # Shared constant imported by providers
NEWS_ORDER = "asc"

# ❌ Premature user-facing config for fixed behavior
class PolygonSettings:
    news_limit: int  # avoid until real need
    news_order: str  # avoid; asc is required for incremental
```

### IMPORTS_ABSOLUTE
Always absolute. Default to package facades for public APIs.
```python
# ✅ from data.storage import commit_llm_batch  # Public via facade
# ✅ from data.storage.db_context import _cursor_context  # Private from source
# ✅ from data.providers.finnhub import FinnhubNewsProvider  # Specific provider
# ❌ from .storage import anything  # Never relative
```

### IMPORT_PLACEMENT
All imports at module level (top of file). Function-level imports allowed ONLY for:
- Optional dependencies (with try/except)
- Breaking circular dependencies (document why inline)
```python
# DEFAULT: Everything at module level
import json
from data.storage import commit_llm_batch
from utils.http import get_json_with_retry
from data.models import NewsItem  # Even if used in one function

def process():
    # RARE EXCEPTION: Only if circular dependency
    # from data.models import NewsItem  # Document why!
    return NewsItem(...)
```

### FACADES_THIN
Keep `__init__.py` thin, side-effect free, explicit `__all__`.
- **Never re-export `_private` helpers** - import them from the defining module when needed
- Top of each package `__init__.py` should be a single short docstring line describing the package; avoid extra commentary comments.

### NAMING_CONVENTIONS
- Modules/functions: `snake_case`
- Classes: `PascalCase`  
- Constants: `UPPER_SNAKE`
- Private: `_leading_underscore`

### TYPE_ANNOTATIONS
Use built-in generics. Preserve type parameters when converting.
```python
def process(items: list[str]) -> dict[str, int | None]:
    ...
# Keep from typing: Mapping, Any, Callable, Awaitable, Iterator, TypeVar
```

### LIST_VS_SEQUENCE
- Default to `list[...]` for concrete collections and return types.
- Use `Sequence[...]` only for parameters that are read-only views (iterate/index/len only, no mutation).

### MAPPING_VS_DICT
Use `Mapping` for read-only inputs; `dict` for mutable locals/returns.

### KEYWORD_ONLY_ARGS
Use `*` for clarity when needed.

### DATETIME_HANDLING
Always UTC timezone-aware. Never format timestamps by hand.
```python
# Flow: API input → normalize_to_utc() → _datetime_to_iso() → SQLite ISO+Z
from utils.datetime_utils import normalize_to_utc

class NewsItem:
    def __init__(self, published: datetime):
        self.published = normalize_to_utc(published)  # Always normalize
```

### MONEY_PRECISION
Use Decimal for money. Avoid binary floats.

### PERSISTENCE
Validate at write boundaries. Choose stable representations. Version schemas clearly.

### DATABASE_SQLITE
Always use `_cursor_context` for all operations.

### ASYNC_PATTERNS
Use async for I/O. Never block in async paths.
```python
async def fetch_all(symbols):
    # get_running_loop() fails fast if called outside async context (surfaces bugs)
    loop = asyncio.get_running_loop()  # NOT get_event_loop()
    tasks = [fetch_one(s) for s in symbols]
    return await asyncio.gather(*tasks)
```

### LOGGING_LAYERED
Module-level loggers with appropriate levels.
- **Avoid duplicate logging across layers** - provider logs details, orchestrator only summarizes
- **Use lazy formatting for all log messages** (e.g., `logger.info("... %s", value)`) so string interpolation is skipped when the log level is off (common for DEBUG)
```python
logger = logging.getLogger(__name__)

# Provider layer:
logger.debug("Skipping item for %s: %s", symbol, reason)  # Expected drops
logger.warning("Failed to fetch %s", symbol)  # Request failures
# Let exceptions propagate to orchestrators

# Orchestrator layer:
logger.info("Processed %s items", count)  # Success summaries only!
logger.exception("Workflow failed")  # In except blocks for stack trace

# Use logger.exception() instead of logger.error(..., exc_info=True) for clarity
```

### DOCSTRINGS_REQUIRED
- **Production code (Summary generation)**: Anything that will be selected into the autogenerated Summary inventory MUST have a docstring (including `_private`):
  - Module docstring (top of file)
  - All module-level classes and functions
  - All class methods
  - **Not selected**: nested functions/classes (defined inside other functions/methods) — add docstrings only when important or non-trivial
- **Tests**: Anything that appears in `docs/Test_Catalog.md` MUST have a docstring:
  - The module-level docstring for each `tests/**/*.py` file (used as "Purpose" in the catalog)
  - All pytest fixtures (top-level `@pytest.fixture` functions)
  - All collected test functions and test methods (names starting with `test_`)
- Helper classes and their internal methods that are not fixtures or tests do not need docstrings for catalog purposes.
- Classes, modules, and package `__init__.py` files SHOULD have a short top-level docstring describing their purpose.
- Keep docstrings short, stable, and behavior-focused; follow `COMMENT_STYLE` for formatting.
```python
def fetch_table_names(db_path: str) -> list[str]:
    """Return sorted SQLite table names for the given database path."""
    ...
```

# SHOULD-FOLLOW RULES
---

### COMMENT_STYLE
- Functions and methods covered by `DOCSTRINGS_REQUIRED` MUST have a docstring; use comments only for extra intent, edge cases, or non-obvious decisions.
- Prefer one-line, stable docstrings that describe behavior/contract; avoid narrative multi-line stories or banners that just restate code.
- Docstrings MUST be "absolute": describe behavior and responsibilities, not how or why the code was written (no meta text like "follow Writing_Code.md" or "this was recently refactored").
- For non-trivial contracts, extra explanation MUST go under a short `"Notes:"` block instead of free-form paragraphs or big `Args`/`Returns` sections (only add those when explicitly requested).
- Follow the surrounding file's commenting style so sections read consistently.

# CODE REVIEW CHECKLIST

### Correctness
- [ ] Timezones UTC-aware with proper units?
- [ ] Money using Decimal not float?
- [ ] Error paths covered with explicit handling?
- [ ] Retries/backoff where needed?

### Consistency
- [ ] Absolute imports following patterns?
- [ ] Using `_cursor_context` for SQLite?
- [ ] Following naming conventions?
- [ ] Matches surrounding style?

### Design
- [ ] Right abstraction level?
- [ ] Clean boundaries, no circular deps?
- [ ] No premature generalization?

### Security/Performance
- [ ] No secrets in code/logs?
- [ ] Input validation at boundaries?
- [ ] Batch external calls?
- [ ] Respect rate limits/timeouts?
- [ ] Avoid unnecessary allocations?

---

## Import Decision Tree
```
Public API? → facade import
Private (_)? → import from source module
Circular dep? → function-level with comment
Optional dep? → function-level with try/except
```

## Logging Levels
```
DEBUG: Expected failures (invalid data)
WARNING: Partial failures (request failed)
ERROR: Workflow failures  
EXCEPTION: Bugs (auto stack trace)
```
