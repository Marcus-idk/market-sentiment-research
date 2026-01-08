# Test Organization Guide

Note: For a complete inventory of all tests (files and test functions), see `docs/Test_Catalog.md`.

---

## REFERENCE FILES (REQUIRED)

These files demonstrate all style rules below. When writing or cleaning up tests, match their patterns:

- **Unit - With DB**: `tests/unit/data/storage/test_storage_news.py`
- **Unit - Contract Tests**: `tests/unit/data/providers/shared/test_news_company_shared.py`
- **Unit - Pure Logic**: `tests/unit/data/models/test_news_models.py`
- **Integration - E2E Workflow**: `tests/integration/data/test_roundtrip_e2e.py`
- **Integration - Live Network**: `tests/integration/data/providers/test_finnhub_live.py`

---

## HOW TO EXTEND THIS DOCUMENT
- Add patterns to appropriate section
- Format: `### PATTERN_NAME` → when to use → example
- Keep decision trees updated
- Reference actual test files that demonstrate pattern

---

## Test Style Guide — Consistency Checks

Use these rules across all tests to keep the suite readable and uniform.

- Catalog + collection note
  - Pytest only collects tests from files matching the default patterns (e.g., `test_*.py` / `*_test.py`).
  - `tools/generate_test_catalog.py` lists every `tests/**/*.py` file. If pytest is installed, it uses pytest collection; otherwise it falls back to name-based AST scanning (best effort).
  - Do not name helper functions `test_*` in non-test modules (e.g., `tests/helpers.py`); keep helpers named like `make_*` / `build_*`, or rename the file to a test-pattern name if it contains real tests.

- Assertions
  - ✅ Prefer plain `assert` without custom failure strings — pytest shows values/diffs.
  - ❌ Remove: `assert len(items) == 2, "Expected 2 items"` (pytest shows this)
  - ✅ Keep: `assert created_at == original, "upsert should preserve created_at"` (business rule)

- Exceptions
  - Use `pytest.raises(ExpectedError, match=...)` when asserting both type and message.

- Setup and builders
  - ✅ Prefer shared factories from `tests/factories/models.py` for common data model shapes; wrap them locally only when the scenario needs extra behaviour or defaults.
  - ❌ Avoid: Inline object construction repeated across multiple tests

# WHERE TO PUT YOUR TEST - PRIMARY DECISION

```
Is it unit or integration test?
├── UNIT TEST → tests/unit/ (mirrors source structure exactly)
│   └── Continue to "Unit Test Organization Rules"
└── INTEGRATION TEST → tests/integration/ (organized by workflow/feature)
    ├── Mark with @pytest.mark.integration
    ├── Name files as test_<workflow>.py
    ├── Parametrize providers via fixtures when sharing behavior
    └── STOP — do not mirror source structure here
```

### Shared Multi-Provider Workflows (optional subfolder)
When several providers share the same live workflow, keep files workflow-named and provider-parametrized. You may group them under a subfolder (e.g., `shared/`) to signal shared behavior intent, as long as:
- Files remain workflow-anchored (e.g., `test_llm_web_search.py`), with an optional `_shared` suffix to denote shared behavior (e.g., `test_llm_web_search_shared.py`)
- Module-level markers include `@pytest.mark.integration` (and `@pytest.mark.network` if networked)
- `tests/integration/llm/conftest.py` exposes a provider spec fixture with ids for readable node IDs

---

## Markers: integration, network, asyncio

- Integration tests: set once per package.
  - tests/integration/conftest.py
  - Keep `pytest.mark.network` only on modules that really hit the network.

- Async-heavy tests: mark the module.
  - Put this at the top of async-heavy files (e.g., provider shared tests):
  - This is the simplest, explicit approach. It avoids repeating `@pytest.mark.asyncio` on every test.

- Network mark: keep it local.
  - Only on tests that perform real HTTP calls: `pytestmark = [pytest.mark.network]` (module-level) or `@pytest.mark.network` (function-level).

## Decision Tree for Unit Tests
```
What's in your source file?
├── CLASSES ONLY → Rule 1: Test<ClassName> for each class
│   └── Multiple similar classes with same behavior? → Rule 6: Shared behavior tests
├── FUNCTIONS ONLY → Rule 2: Split by feature into test_<module>_<feature>.py
├── BOTH → Rule 3: Test<ClassName> + test_<module>_functions.py
├── ABSTRACT BASE CLASSES → Rule 4: Test<ClassName>Contract
└── ENUMS → Rule 5: test_enum_values_unchanged()
```

## Rule 1: Classes Get 1:1 Mapping
```python
# Source: data/providers/finnhub/finnhub_client.py
class FinnhubClient:
    ...
class FinnhubNewsProvider:
    ...

# Tests: split by concern
# tests/unit/data/providers/shared/test_client_shared.py
class TestClientShared:
    ...
# tests/unit/data/providers/test_finnhub_news.py
class TestFinnhubNewsProvider:
    ...
# tests/unit/data/providers/test_finnhub_prices.py
class TestFinnhubPriceProvider:
    ...
# tests/unit/data/providers/test_finnhub_macro.py
class TestFinnhubMacroProviderSpecific:
    ...
```
## Rule 2: Functions Get Feature Groups
```python
# Source: data/storage/storage_crud.py (25+ functions)
def store_news_items(): ...
def get_news_since(): ...
def store_price_data(): ...
def get_price_data_since(): ...
# ... 20+ more functions

# Tests: Split by feature
# tests/unit/data/storage/test_storage_news.py
class TestNewsStorage:
    def test_store_news_items_valid(): ...
    def test_get_news_since_returns_sorted(): ...

# tests/unit/data/storage/test_storage_prices.py
class TestPriceStorage:
    def test_store_price_data_valid(): ...
```

## Rule 3: Mixed Files Get Both
```python
# Source: utils/helpers.py
class CacheManager: ...
def normalize_string(): ...
def validate_input(): ...

# Tests:
# tests/unit/utils/test_helpers.py
class TestCacheManager:  # 1:1 for class
    ...

# tests/unit/utils/test_helpers_functions.py
class TestStringHelpers:  # Or plain functions
    def test_normalize_string(): ...
```

## Rule 4: ABCs Get Contract Tests
```python
# Source: data/base.py
class DataSource(ABC):
    @abstractmethod
    def fetch(): ...

# Test: tests/unit/data/test_data_base.py
class TestDataSourceContract:
    def test_all_implementations_have_fetch(): ...
    def test_fetch_returns_expected_type(): ...
```
✅ Tests the contract, not forcing 1:1  
❌ Bad: TestDataSource (meaningless for ABCs)

## Rule 5: Enums Need Value Lock Tests
```python
# Source: data/models.py
class Session(Enum):
    REG = "REG"
    PRE = "PRE"
    POST = "POST"
    CLOSED = "CLOSED"

# Test: tests/unit/data/models/test_price_and_analysis_models.py
def test_enum_values_unchanged():
    """These values are in database - MUST NOT CHANGE."""
    assert Session.REG.value == "REG"
    assert Session.PRE.value == "PRE"
    assert Session.POST.value == "POST"
    assert Session.CLOSED.value == "CLOSED"
```
✅ Prevents someone changing "REG" to "REGULAR" and breaking DB

## Rule 6: Repeated Behavior Uses Shared Behavior Tests
When multiple similar classes share identical behavior, use shared behavior tests instead of copying tests.

### When to Use Shared Behavior Tests
- ✅ **Same behavior across providers (when 2+ exist)**: Use shared behavior tests
- ✅ **Multiple implementations of same interface**: Different provider implementations
- ✅ **Shared validation logic**: All providers validate connections the same way
- ❌ **Provider-specific quirks**: Pagination details, endpoint paths (keep separate)

### References
- Data ABC contract tests: `tests/unit/data/test_data_base.py`
- LLM ABC contract tests: `tests/unit/llm/test_llm_base.py`
- Provider shared tests: `tests/unit/data/providers/shared/`

---

# INTEGRATION TEST ORGANIZATION

## Structure by Feature/Workflow
```
tests/integration/
├── data/
│   ├── providers/              # live/data-source workflows
│   ├── test_<workflow>.py      # e.g., test_roundtrip_e2e.py
│   └── ...
└── llm/
    ├── helpers.py                      # shared utilities
    ├── conftest.py                     # provider specs/fixtures
    ├── test_llm_connection_and_generate.py
    ├── test_llm_code_execution.py
    └── test_llm_web_search.py
```

## Integration Test Rules
- Organize by FEATURE/WORKFLOW, not source structure
- Always mark with `@pytest.mark.integration`
- Can use real databases, APIs (in integration only!)
- Test complete workflows, not individual functions

---

## SQLite Helper Usage
Prefer `_cursor_context` for all operations.
```python
from data.storage.db_context import _cursor_context

# ✅ Good for reads
with _cursor_context(db_path, commit=False) as cursor:
    cursor.execute("SELECT * FROM items")
    
# ✅ Good for writes (default commit=True)
with _cursor_context(db_path) as cursor:
    cursor.execute("INSERT INTO items VALUES (?)", (data,))

# ❌ Avoid direct connect() unless:
# - init_database() / finalize_database()
# - Connection-level PRAGMAs (e.g., WAL checkpoint)
```

## Monkeypatching vs Direct Assignment
Choose the right mocking approach based on what you're replacing.

### Rule: Mock imports, assign to instances
- **Monkeypatch** = Replace module-level imports (names looked up at top of file)
- **Direct assignment** = Replace methods on instances you already have

### When to Use Monkeypatch
Use monkeypatch when testing code that **imports and calls** a function by name.

```python
# Source: data/providers/finnhub/finnhub_client.py
from utils.http import get_json_with_retry  # ← Module-level import

class FinnhubClient:
    async def get(self, path: str):
        # Looks up 'get_json_with_retry' by name in module namespace
        return await get_json_with_retry(url, ...)

# Test: Monkeypatch the IMPORT where it's looked up
def test_client(monkeypatch):
    monkeypatch.setattr(
        'data.providers.finnhub.finnhub_client.get_json_with_retry',  # Where client finds it
        mock_function
    )
    client = FinnhubClient(settings)
    await client.get('/quote')  # Uses mocked version
```

### When to Use Direct Assignment
Use direct assignment when testing code that **calls methods on an instance**.

```python
# Source: data/providers/finnhub/finnhub_news.py
class FinnhubNewsProvider:
    def __init__(self, settings, symbols):
        self.client = FinnhubClient(settings)  # ← Creates instance

    async def fetch_incremental(self):
        response = await self.client.get('/company-news')  # ← Calls instance method

# Test: Replace the METHOD on the instance
async def test_provider():
    provider = FinnhubNewsProvider(settings, ['AAPL'])

    async def mock_get(path, params=None):
        return [{'headline': '...', 'url': '...', 'datetime': 123}]

    provider.client.get = mock_get  # ← Direct assignment to instance method
    result = await provider.fetch_incremental()  # Uses mocked version
```

## Current Timestamps vs Frozen Time
Choose the right clock setup for each test.

### Rule: Default to real time for shared behavior; freeze for date math
- **Current timestamps** → use in cross-provider shared behavior tests when freshness is the only concern.
- **Frozen time** → use when asserting date windows, buffer math, or max-id rollovers.
- Prefer the shared `clock` fixture when available; otherwise monkeypatch the provider module's `datetime`.

### When to use current time
Shared behavior tests such as `tests/unit/data/providers/shared/test_news_company_shared.py` keep `datetime.now()` so the date window still returns the sample article. Nothing in that test asserts the exact timestamp.

### When to freeze time
Provider-specific tests like `tests/unit/data/providers/test_finnhub_macro.py` freeze `datetime.now()` before calling the provider. That makes date math (e.g., buffer windows) deterministic.

### No Forced Passes
- Tests must fail on real regressions; do not hide failures.
- Do not catch broad exceptions in tests; assert specific errors with `pytest.raises`.
- Do not use `@pytest.mark.skip`/`xfail` without a concrete, documented reason.
- Avoid trivial assertions (e.g., `assert True`); validate outputs and side effects.
- Don’t over-mock to bypass code-under-test logic; mock at boundaries only.

### Shared Test Setup
Initialize shared objects at the class/fixture level, not in every test method. Avoid repeating initialization code.

**Reference**: See `tests/conftest.py` for project-wide fixtures like `temp_db_path`

---

# FILE SIZE & NAMING

## When to Split
- File exceeds 600 lines → MUST split

### Test Methods
```python
# ✅ GOOD: Descriptive
def test_store_news_with_duplicate_url_skips():
def test_price_validation_rejects_negative_values():

# ❌ BAD: Vague
def test_1():
def test_stuff():
```

---

# QUICK CHECKLIST

## Is it in the right location?
- [ ] Unit test? → Mirror source in tests/unit/
- [ ] Integration? → Workflow in tests/integration/
- [ ] Marked correctly? → @pytest.mark.integration, @pytest.mark.network

## Does it follow the pattern?
- [ ] Classes? → 1:1 with TestClassName
- [ ] Multiple similar classes? → Shared behavior tests (Rule 6)
- [ ] Functions? → Split by feature
- [ ] Mixed? → Both patterns
- [ ] ABC? → Contract tests (Rule 4)
- [ ] Enum? → Value lock tests

## Quality checks
- [ ] Test file < 600 lines? (split if not)
- [ ] Test names descriptive?
- [ ] Using _cursor_context for SQLite?
- [ ] Mocking at correct level (not facades)?
- [ ] Integration tests marked correctly?
- [ ] Following similar test patterns? (studied existing tests first?)
- [ ] Simple asserts have no custom message strings
- [ ] Complex assertions use brief messages only when needed
- [ ] Exception tests use `pytest.raises(..., match=...)` when message matters
- [ ] Repeated setup factored into helpers/fixtures

---
