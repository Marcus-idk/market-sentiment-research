# Writing Code Guidelines - LLM-Optimized

## 📝 HOW TO EXTEND THIS DOCUMENT
- Add rules under appropriate section (MUST/SHOULD)
- Format: `### RULE_NAME` → description → example
- Keep examples minimal but demonstrative
- Test that examples work before adding

---

## PROJECT CONTEXT
- **Python Version**: 3.13.4 (target 3.13+)
- **Principle**: Follow existing patterns. Propose improvements only when they clearly reduce complexity.
- **Scope**: All new/changed code

---

# MUST-FOLLOW RULES

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
```python
# SCENARIO: Implementing PolygonNewsProvider
# STEP 1: Find similar code → FinnhubNewsProvider exists
# STEP 2: Study its structure
#   ✅ Copy: class structure, method signatures, error handling patterns
#   ✅ Copy: logging approach (debug for skips, warning for failures)
#   ✅ Copy: buffer_time logic, symbol iteration, NewsItem construction
#   ✅ Copy: variable names (use `articles` not `results` if similar code uses `articles`)
#   ✅ Copy: comment style ("# Parse articles" matches existing pattern)
#   ✅ Copy: log message format ("Failed to parse macro news article" for consistency)
#   ❌ Don't blindly copy: min_id parameter (Finnhub macro uses ID-based cursor, Polygon uses time-based)
#   ❌ Don't blindly copy: MAX_PAGES constant (different pagination approach)

# ✅ GOOD: Thoughtful consistency (matches variable names, comments, style)
class PolygonNewsProvider(NewsDataSource):
    async def fetch_incremental(self, *, since: datetime | None = None):
        # Polygon only needs time-based filtering
        buffer_time = since - timedelta(minutes=2)
        published_gt = _datetime_to_iso(buffer_time)

        articles = response.get("results", [])  # Use 'articles' like Finnhub does
        # Parse articles  # Same comment style
        for article in articles:
            # ... follows Finnhub's error handling and logging patterns

# ❌ BAD: Blind copying
class PolygonNewsProvider(NewsDataSource):
    async def fetch_incremental(self, *, since: datetime | None = None, min_id: int | None = None):
        # Copied min_id from Finnhub but never use it - WRONG!
        # Polygon API doesn't support ID-based cursors

        results = response.get("results", [])  # Inconsistent naming
        for article in results:  # Different variable name than similar code
```

### DRY_PRINCIPLE
Avoid duplication when abstraction is real. Avoid premature abstraction.
```python
# ✅ _datetime_to_iso() used 10+ times - good abstraction
# ❌ extract_number() used once - premature
```

### NO_DEAD_CODE
Remove unused variables, imports, and functions. Keep function signatures consistent with base contracts even if some parameters aren’t used by a specific implementation (document that they’re ignored).
```python
# ✅ GOOD: Keep unified provider contract; ignore irrelevant cursors
async def fetch_incremental(self, *, since: datetime | None = None, min_id: int | None = None):
    # Date-based provider: ignore min_id (ID-based cursor not supported)
    buffer_time = since - timedelta(minutes=2) if since else None
    published_gt = _datetime_to_iso(buffer_time) if buffer_time else None
    ...

# ❌ BAD: Diverging signature breaks orchestrator/generic calls
async def fetch_incremental(self, *, since: datetime | None = None):  # Missing min_id
    ...

# ❌ BAD: Unused imports
import json  # Never used
from typing import Dict  # Never used

# ❌ BAD: Defensive code that serves no purpose
if min_id is not None:
    pass  # Does nothing, parameter ignored

# Remove it entirely - if code isn't defensive or functional, delete it
```

Defensive checks for external contracts must log a warning or raise when triggered; otherwise remove them.

```python
# ✅ GOOD: Assert external API contract with visible signal
if buffer_time and published <= buffer_time:
    logger.warning(
        f"Provider returned item at/before cutoff {published} (filter gt {buffer_time})"
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
    # Use dataclasses/enums where helpful
```

### ERROR_HANDLING
Handle errors explicitly. Never swallow. Raise domain-specific exceptions.
```python
try:
    response = api_call(symbol)
except RequestException as e:
    logger.exception(f"Failed to fetch {symbol}")
    raise DataFetchError(f"Cannot retrieve {symbol}: {e}") from e
```

Fail‑fast for structural errors; degrade gracefully for malformed items; empty pages are valid termination.

```python
# Structural/contract errors → raise immediately
if not isinstance(response, dict):
    raise DataFetchError(f"Expected dict, got {type(response).__name__}")

results = response.get("results", [])
if not isinstance(results, list):
    raise DataFetchError("results must be list")

# Valid "no data" case → stop cleanly
if not results:
    return []

# Malformed items → skip with DEBUG log
for article in results:
    try:
        items.extend(parse_article(article))
    except Exception as exc:
        logger.debug(f"Skipping malformed item: {exc}")
```

### ERROR_HANDLING_EXPECTED_PARSING
Parsing helpers may return sentinel values (e.g., `None`) without logging when a comment documents the intentional fallthrough and the function contract defines the sentinel.
```python
def parse_retry_after(value: str | float | int | None) -> float | None:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        # Intentional fallthrough: try HTTP-date parsing next.
        pass
    ...
    return None
```

### ORCHESTRATOR_TIMEOUTS
Polling loops must log normal timeout or cancellation signals instead of silently swallowing them.
```python
except asyncio.TimeoutError:
    logger.debug("Poll wait timeout; continuing")
```

### CLEANUP_SHUTDOWN
Before escalating from graceful shutdown to forceful termination, emit a `WARNING` with the cause.
```python
except Exception as exc:
    logger.warning(f"Graceful stop failed; forcing kill: {exc}")
    process.kill()
```

### PER_ITEM_CATCHES
Per-item parsing loops should catch explicit data issues (`ValueError`, `TypeError`, `KeyError`, `AttributeError`, and provider-domain errors) instead of `except Exception`.
```python
except (ValueError, TypeError, KeyError, AttributeError, DataSourceError) as exc:
    logger.debug(f"Skipping malformed item: {exc}")
```

### CAUSE_CHAINING
When wrapping exceptions, use `raise ... from exc` so upstream callers retain the original traceback.
```python
except SDKError as exc:
    raise DataSourceError("Provider failed") from exc
```

### CENTRALIZE_CONCERNS
Centralize I/O, HTTP, retries/backoff, timezones, data normalization, logging.
**ALWAYS check `utils/` and `data/storage/storage_utils.py` for existing helpers before writing new code.**
```python
# ✅ GOOD: Use existing utilities
from utils.http import get_json_with_retry  # Don't reimplement retry logic
from data.models import _normalize_to_utc  # Don't reimplement TZ handling
from data.storage.storage_utils import _datetime_to_iso  # Don't manually format ISO strings
from utils.market_sessions import classify_us_session  # Don't reimplement session logic

# ❌ BAD: Reimplementing existing utilities
published_gt = buffer_time.isoformat().replace("+00:00", "Z")  # _datetime_to_iso exists!
# Custom retry logic with exponential backoff  # get_json_with_retry exists!
```

Timestamp parsing: prefer shared helpers for RFC3339/ISO conversions; don’t duplicate parsing across providers.

```python
# ✅ GOOD: Centralize parsing
from data.storage.storage_utils import _parse_rfc3339, _datetime_to_iso
published = _parse_rfc3339(ts_str)
published_iso = _datetime_to_iso(published)

# ❌ BAD: Repeating multi-branch parsing logic inline in providers
```

### BOUNDARIES_CLEAN
Keep layers clean. Avoid circular dependencies.
```
Configuration → Adapters/Clients → Models/Storage → Services/Workflows
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
_NEWS_LIMIT = 100
_NEWS_ORDER = "asc"

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
```python
"""Data providers package."""
from data.providers.finnhub import FinnhubNewsProvider

__all__ = ["FinnhubNewsProvider"]  # Only public names, no _private exports

# When you need a private helper:
# from data.storage.db_context import _cursor_context  # Import from source
```

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

### KEYWORD_ONLY_ARGS
Use `*` for clarity when needed.
```python
# Use when: 4+ optional params, similar types, boolean flags, multiple cursors
def fetch(url, *, timeout=30, max_retries=3, validate=True):
    ...
# Don't use for: simple 1-3 params, obvious order, dataclasses
```

### DATETIME_HANDLING
Always UTC timezone-aware. Never format timestamps by hand.
```python
# Flow: API input → normalize_to_utc() → _datetime_to_iso() → SQLite ISO+Z
from data.models import _normalize_to_utc

class NewsItem:
    def __init__(self, published: datetime | str):
        self.published = _normalize_to_utc(published)  # Always normalize
```

### MARKET_SESSIONS
Use standard classifier for US sessions.
```python
from utils.market_sessions import classify_us_session
session = classify_us_session(timestamp)  # Returns PRE/REG/POST/CLOSED
# Handles NYSE holidays, early closes, UTC→ET conversion
```

### MONEY_PRECISION
Use Decimal for money. Avoid binary floats.
```python
from decimal import Decimal
price = Decimal("150.25")  # Never float for money
```

### PERSISTENCE
Validate at write boundaries. Choose stable representations. Version schemas clearly.

### DATABASE_SQLITE
Always use `_cursor_context` for all operations.
```python
from data.storage.db_context import _cursor_context

with _cursor_context(db_path) as cursor:
    cursor.execute("INSERT INTO items VALUES (?)", (data,))
# Auto-commit, foreign keys, row factory, cleanup

# Exceptions: Only direct connect() for:
# - init_database() / finalize_database()
# - Connection-level PRAGMAs (document why)
```

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
Module-level loggers with appropriate levels. Use f-strings.
- **Avoid duplicate logging across layers** - provider logs details, orchestrator only summarizes
```python
logger = logging.getLogger(__name__)

# Provider layer:
logger.debug(f"Skipping item for {symbol}: {reason}")  # Expected drops
logger.warning(f"Failed to fetch {symbol}")  # Request failures
# Let exceptions propagate to orchestrators

# Orchestrator layer:
logger.info(f"Processed {count} items")  # Success summaries only!
logger.exception("Workflow failed")  # In except blocks for stack trace

# Use logger.exception() instead of logger.error(..., exc_info=True) for clarity
```

### TESTING_REQUIRED
Add/adjust tests for every change.
- Prefer explicit clock helpers over monkeypatching time/datetime
- Follow project testing conventions
- Mark slower integration/network tests
- Monkeypatch where symbol is looked up (module under test), not facades

### DOCUMENTATION
Update docs when public APIs, schemas, or test structure change.
- Brief comments explain "why" not "what"
- Keep README links valid
- Prefer small, focused tests with clear names

---

# SHOULD-FOLLOW RULES

### REUSE_FIRST
Will this be reused soon? If yes, follow existing interfaces. If no, keep local and simple.

### COMMENTS_BRIEF
```python
# Batch size of 100 to stay under API rate limits
BATCH_SIZE = 100

# Import here to avoid circular dependency with models
from data.models import NewsItem
```

---

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

# QUICK REFERENCE

## Import Decision Tree
```
Public API? → facade import
Private (_)? → import from source module
Circular dep? → function-level with comment
Optional dep? → function-level with try/except
```

## Type Conversion Table
| Old typing | New built-in |
|------------|--------------|
| List[str] | list[str] |
| Dict[str, Any] | dict[str, Any] |
| Optional[int] | int \| None |
| Union[str, int] | str \| int |
| Tuple[...] | tuple[...] |

## Datetime Flow
```
Input → _normalize_to_utc() → _datetime_to_iso() → SQLite ISO+Z
```

## Logging Levels
```
DEBUG: Expected failures (invalid data)
WARNING: Partial failures (request failed)
ERROR: Workflow failures  
EXCEPTION: Bugs (auto stack trace)
```
