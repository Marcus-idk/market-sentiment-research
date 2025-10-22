# Test Organization Guide - LLM-Optimized

Note: For a complete inventory of all tests (files and test functions), see `docs/Test_Catalog.md`.

## 📝 HOW TO EXTEND THIS DOCUMENT
- Add patterns to appropriate section
- Format: `### PATTERN_NAME` → when to use → example
- Keep decision trees updated
- Reference actual test files that demonstrate pattern

---

## LIMITS & FRAMEWORK
- **Max file size**: 600 lines (target: ~400)
- **Max test class**: ~200-250 lines
- **Framework**: pytest
- **Principle**: Make it obvious where to find/add tests

---

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


---

## Markers: integration, network, asyncio

- Integration tests: set once per package.
  - tests/integration/conftest.py
    ```python
    import pytest
    pytestmark = pytest.mark.integration
    ```
  - Keep `pytest.mark.network` only on modules that really hit the network.

- Async-heavy tests: mark the module.
  - Put this at the top of async-heavy files (e.g., provider shared tests):
    ```python
    import pytest
    pytestmark = pytest.mark.asyncio
    ```
  - This is the simplest, explicit approach. It avoids repeating `@pytest.mark.asyncio` on every test.

- Advanced (optional): directory-wide asyncio via a conftest hook.
  - Use only if an entire folder is async and you want zero per-file marks.
  - tests/unit/data/providers/shared/conftest.py
    ```python
    import pytest

    def pytest_collection_modifyitems(config, items):
        for item in items:
            if 'tests/unit/data/providers/shared' in str(item.fspath):
                item.add_marker(pytest.mark.asyncio)
    ```
  - Note: a plain `pytestmark = pytest.mark.asyncio` inside a conftest.py does not auto-apply to other modules; use the hook above if you need folder-wide behavior.

- Network mark: keep it local.
  - Only on tests that perform real HTTP calls: `pytestmark = [pytest.mark.network]` (module-level) or `@pytest.mark.network` (function-level).

- Examples in repo:
  - Package integration mark: `tests/integration/conftest.py`
  - Module asyncio mark: `tests/unit/data/providers/shared/test_prices_shared.py`
  - Network modules: `tests/integration/llm/shared/test_llm_connection_shared.py`# UNIT TEST ORGANIZATION RULES

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
✅ Easy to find: "Where's the Finnhub client test?" → TestClientShared  
❌ Bad: TestFinnhubStuff, TestNewsFeatures

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
✅ Files stay under 400 lines, organized by function  
❌ Bad: One giant 1200-line file

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

# Test: tests/unit/data/test_models.py
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
- ✅ **Same behavior, different data format**: Finnhub vs Polygon news parsing
- ✅ **Multiple implementations of same interface**: Different provider implementations
- ✅ **Shared validation logic**: All providers validate connections the same way
- ❌ **Provider-specific quirks**: Pagination details, endpoint paths (keep separate)

### Pattern
```python
# tests/unit/data/providers/conftest.py
@pytest.fixture
def provider_specs():
    """Specs for all news providers"""
    return [
        ProviderSpec(
            name='finnhub',
            provider_cls=FinnhubNewsProvider,
            settings=FinnhubSettings(api_key='test_key'),
            symbols=['AAPL'],
            make_valid_article=lambda: {
                'headline': 'Breaking News',
                'url': 'https://example.com/news',
                'datetime': 1705320000,  # Epoch
                'source': 'Reuters',
                'summary': 'Article content'
            },
            make_missing_headline=lambda: {
                'url': 'https://example.com/news',
                'datetime': 1705320000
            }
        ),
        ProviderSpec(
            name='polygon',
            provider_cls=PolygonNewsProvider,
            settings=PolygonSettings(api_key='test_key'),
            symbols=['AAPL'],
            make_valid_article=lambda: {
                'title': 'Breaking News',  # Different field name
                'article_url': 'https://example.com/news',
                'published_utc': '2024-01-15T12:00:00Z',  # RFC3339
                'publisher': {'name': 'Reuters'},
                'description': 'Article content'
            },
            make_missing_headline=lambda: {
                'article_url': 'https://example.com/news',
                'published_utc': '2024-01-15T12:00:00Z'
            }
        )
    ]

# tests/unit/data/providers/shared/test_news_company_shared.py
class TestNewsCompanyShared:
    """Shared behavior tests for all company news providers"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("spec", provider_specs())
    async def test_skips_missing_headline(self, spec):
        """All providers skip articles without headlines"""
        provider = spec.provider_cls(spec.settings, spec.symbols)

        # Mock provider's client with spec-specific data format
        async def mock_get(path, params=None):
            return [spec.make_missing_headline()]

        provider.client.get = mock_get

        # Behavior is identical across providers
        results = await provider.fetch_incremental()
        assert len(results) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("spec", provider_specs())
    async def test_parses_valid_article(self, spec):
        """All providers parse valid articles correctly"""
        provider = spec.provider_cls(spec.settings, spec.symbols)

        async def mock_get(path, params=None):
            return [spec.make_valid_article()]

        provider.client.get = mock_get

        results = await provider.fetch_incremental()
        assert len(results) == 1
        assert results[0].symbol == 'AAPL'
        assert results[0].headline == 'Breaking News'
        assert results[0].url == 'https://example.com/news'
```

### What Goes Where

**Shared behavior** → `tests/unit/data/providers/shared/test_*.py`
- Skips missing headlines (same logic, different data format)
- Filters old articles with 2-minute buffer
- Validation success/failure
- Structural error handling (non-list response)

**Provider-specific** → `tests/unit/data/providers/test_<provider>_*.py`
- Polygon cursor pagination
- Finnhub minId tracking
- Endpoint paths and URL construction
- Provider-specific field extraction quirks

### ProviderSpec Structure
```python
@dataclass
class ProviderSpec:
    """Specification for parametrizing provider shared behavior tests"""
    name: str                           # 'finnhub', 'polygon'
    provider_cls: type                  # FinnhubNewsProvider
    settings: Any                       # FinnhubSettings instance
    symbols: list[str]                  # ['AAPL', 'MSFT']

    # Factory methods for test data in provider's format
    make_valid_article: callable        # Returns dict in provider's API format
    make_missing_headline: callable     # Missing required field
    make_invalid_timestamp: callable    # Invalid timestamp format
    # ... other edge case factories
```

### Benefits
✅ **Write once, test all**: Shared behavior tested across all providers automatically
✅ **Add provider easily**: New provider = add spec, get all shared tests free
✅ **Clear separation**: See what's shared vs unique at a glance
✅ **Less duplication**: No copy-pasting identical tests

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
*Illustrative structure - use as pattern, not exact inventory*

## Integration Test Rules
- Organize by FEATURE/WORKFLOW, not source structure
- Always mark with `@pytest.mark.integration`
- Live/network tests also use `@pytest.mark.network`
- Can use real databases, APIs (in integration only!)
- Test complete workflows, not individual functions

## Networked Live Tests
```python
# Required environment variables
FINNHUB_API_KEY     # Finnhub live checks
OPENAI_API_KEY      # OpenAI provider tests
GEMINI_API_KEY      # Gemini provider tests

# Skip gracefully when missing
@pytest.mark.skipif(
    not os.getenv("FINNHUB_API_KEY"),
    reason="FINNHUB_API_KEY not set"
)
def test_finnhub_live():
    ...
```

---

# TEST PATTERNS

## FOLLOW_SIMILAR_TESTS → Study existing tests before writing new ones
When writing tests for similar functionality, find and study the existing test implementation. Follow its structure, patterns, and conventions—including test naming, mock setup, assertion style, and organization—but don't blindly copy tests that don't apply to your use case.

**Pattern:**
1. Find similar test file (e.g., testing PolygonClient? → look at shared/test_client_shared.py)
2. Study its structure: class names, test method names, mock patterns, assertions
3. Copy what applies: naming conventions, mock setup patterns, assertion patterns
4. Adapt what doesn't: API differences, different behaviors, different error types

**Example:**
```python
# SCENARIO: Writing tests for PolygonNewsProvider
# STEP 1: Find similar tests → test_finnhub_news.py exists

# STEP 2: Study test structure
# From test_finnhub_news.py:
class TestFinnhubNewsProvider:
    async def test_parses_valid_article(self):
        news_fixture = [{
            'headline': 'Tesla Stock Rises',
            'url': 'https://example.com/tesla-news',
            'datetime': 1705320000,  # Epoch
            'source': 'Reuters',
            'summary': 'Tesla stock rose 5% today.'
        }]
        # ... rest of test

# STEP 3: Copy structure and naming for Polygon tests
# ✅ Copy: test class name pattern (TestPolygonNewsProvider)
# ✅ Copy: test method name pattern (test_parses_valid_article)
# ✅ Copy: mock setup pattern (provider.client.get = AsyncMock(...))
# ✅ Copy: assertion style (assert result.symbol == 'AAPL')
# ❌ Don't copy: Field names (Polygon uses 'title' not 'headline')
# ❌ Don't copy: Timestamp format (Polygon uses RFC3339 not epoch)

class TestPolygonNewsProvider:
    async def test_parse_article_valid(self):  # Same naming pattern
        article = {
            'title': 'Apple Announces iPhone',      # Polygon field name
            'article_url': 'https://example.com/1', # Polygon field name
            'published_utc': '2024-01-15T12:00:00Z', # RFC3339, not epoch
            'publisher': {'name': 'TechCrunch'},
            'description': 'Apple unveils...'
        }
        # Same assertion pattern as Finnhub tests
        assert result.symbol == 'AAPL'
        assert result.headline == 'Apple Announces iPhone'
```

**Key Benefits:**
- Consistent test style across similar modules
- Faster test development (copy proven patterns)
- Easier code review (reviewers recognize patterns)
- Reduced bugs (proven test patterns work)

**When to Study Similar Tests:**
- ✅ Writing provider tests → Study other provider tests
- ✅ Writing storage tests → Study other storage tests
- ✅ Writing LLM tests → Study existing LLM tests
- ✅ Adding new test to existing file → Match that file's style

**References:**
- Provider tests: `tests/unit/data/providers/shared/test_client_shared.py`, `tests/unit/data/providers/test_finnhub_prices.py`, `tests/unit/data/providers/test_finnhub_news.py`, `tests/unit/data/providers/test_finnhub_macro.py`
- Storage tests: `test_storage_news.py`, `test_storage_prices.py`
- LLM tests: `test_openai_provider.py`, `test_gemini_provider.py`

---

## Testing Retry Logic
Mock HTTP client with response sequences, not the retry wrapper.
```python
# ✅ CORRECT: Mock HTTP responses, verify retry behavior
responses = [
    Mock(status_code=429),
    Mock(status_code=429),
    Mock(status_code=200, json=lambda: {"data": "success"})
]
mock_http_client(mock_get_function)
assert call_count == 3  # Verify retries happened

# ❌ WRONG: Mock retry wrapper only tests delegation
monkeypatch.setattr('get_json_with_retry', mock_success)
assert call_count == 1  # Doesn't test retries!
```
Reference: `tests/unit/utils/test_http.py::test_429_numeric_retry_after`

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
# Source: data/providers/polygon/polygon_client.py
from utils.http import get_json_with_retry  # ← Module-level import

class PolygonClient:
    async def get(self, path: str):
        # Looks up 'get_json_with_retry' by name in module namespace
        return await get_json_with_retry(url, ...)

# Test: Monkeypatch the IMPORT where it's looked up
def test_client(monkeypatch):
    monkeypatch.setattr(
        'data.providers.polygon.polygon_client.get_json_with_retry',  # Where client finds it
        mock_function
    )
    client = PolygonClient(settings)
    await client.get('/quote')  # Uses mocked version
```

### When to Use Direct Assignment
Use direct assignment when testing code that **calls methods on an instance**.

```python
# Source: data/providers/polygon/polygon_news.py
class PolygonNewsProvider:
    def __init__(self, settings, symbols):
        self.client = PolygonClient(settings)  # ← Creates instance

    async def fetch_incremental(self):
        response = await self.client.get('/news')  # ← Calls instance method

# Test: Replace the METHOD on the instance
async def test_provider():
    provider = PolygonNewsProvider(settings, ['AAPL'])

    async def mock_get(path, params=None):
        return {'results': [...]}

    provider.client.get = mock_get  # ← Direct assignment to instance method
    result = await provider.fetch_incremental()  # Uses mocked version
```

### Why This Matters
```python
# ✅ CORRECT: Patch where symbol is looked up
monkeypatch.setattr("data.providers.finnhub.requests.get", mock_get)

# ❌ WRONG: Patching facade module (won't work)
monkeypatch.setattr("data.providers.requests.get", mock_get)

# ✅ CORRECT: Direct assignment when you have the instance
provider.client.get = mock_get

# ❌ WRONG: Monkeypatching instance methods (unnecessarily complex)
monkeypatch.setattr("provider.client.get", mock_get)
```

**Reference**: See `tests/unit/data/providers/test_polygon_macro_news.py` (monkeypatch) vs `tests/unit/data/providers/test_finnhub_news.py` (direct assignment)

## Current Timestamps vs Frozen Time
Choose the right clock setup for each test.

### Rule: Default to real time for shared behavior; freeze for date math
- **Current timestamps** → use in cross-provider shared behavior tests when freshness is the only concern.
- **Frozen time** → use when asserting date windows, buffer math, or max-id rollovers.
- Prefer the shared `clock` fixture when available; otherwise monkeypatch the provider module's `datetime`.

### When to use current time
Shared behavior tests such as `tests/unit/data/providers/shared/test_news_company_shared.py` keep `datetime.now()` so Polygon's 2-day filter still returns the sample article. Nothing in that test asserts the exact timestamp.

### When to freeze time
Provider-specific tests like `tests/unit/data/providers/test_finnhub_macro.py` or `tests/unit/data/providers/test_polygon_macro_news.py` freeze `datetime.now()` before calling the provider. That makes date math (e.g., buffer windows) deterministic.

### Quick reference

| Test Type | Timestamp Approach | Why |
|-----------|-------------------|-----|
| **Shared behavior tests** | Real `datetime.now()` unless the test asserts window edges | Keeps articles inside provider freshness filters |
| **Provider-specific tests** (date logic) | Frozen time via clock fixture/monkeypatch | Validates exact ranges, ids, and buffer math |
| **Live/integration tests** | Real time | Exercises the real service end-to-end |

## Testing Best Practices
- Prefer explicit clock helpers/fixture defaults over monkeypatching time/datetime
- Unnecessary patches add global side effects without increasing coverage
- Follow project testing conventions
- Mark slower integration/network tests
- Avoid duplicate assertions across layers (e.g., DB defaults live in schema tests only)
- Prefer small, focused tests with minimal examples and clear names

### No Forced Passes
- Tests must fail on real regressions; do not hide failures.
- Do not catch broad exceptions in tests; assert specific errors with `pytest.raises`.
- Do not use `@pytest.mark.skip`/`xfail` without a concrete, documented reason.
- Avoid trivial assertions (e.g., `assert True`); validate outputs and side effects.
- Don’t over-mock to bypass code-under-test logic; mock at boundaries only.

### Shared Test Setup
Initialize shared objects at the class/fixture level, not in every test method. Avoid repeating initialization code.

**Using pytest fixtures (Recommended):**
```python
# ✅ GOOD: Shared setup via fixture
@pytest.fixture
def provider():
    """Create provider once, use in all tests"""
    settings = FinnhubSettings(api_key='test_key')
    return FinnhubNewsProvider(settings, ['AAPL', 'MSFT'])

class TestFinnhubNewsProvider:
    def test_validates_connection(self, provider):
        # provider is injected, no setup needed
        assert provider.symbols == ['AAPL', 'MSFT']

    def test_fetches_news(self, provider):
        # Same provider instance (or fresh if fixture has default scope)
        async def mock_get(path, params=None):
            return [...]
        provider.client.get = mock_get
        # ... test logic

# ❌ BAD: Repeating initialization
class TestFinnhubNewsProvider:
    def test_validates_connection(self):
        settings = FinnhubSettings(api_key='test_key')  # Repeated!
        provider = FinnhubNewsProvider(settings, ['AAPL', 'MSFT'])
        assert provider.symbols == ['AAPL', 'MSFT']

    def test_fetches_news(self):
        settings = FinnhubSettings(api_key='test_key')  # Repeated!
        provider = FinnhubNewsProvider(settings, ['AAPL', 'MSFT'])
        # ... test logic
```

**Using class-level setup (Alternative):**
```python
# ✅ GOOD: Setup method runs before each test
class TestFinnhubNewsProvider:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Runs automatically before each test"""
        settings = FinnhubSettings(api_key='test_key')
        self.provider = FinnhubNewsProvider(settings, ['AAPL'])

    def test_validates_connection(self):
        assert self.provider.symbols == ['AAPL']  # Use self.provider

    def test_fetches_news(self):
        self.provider.client.get = mock_get  # Use self.provider
```

**When to share vs duplicate:**
- ✅ **Share**: Immutable setup (settings, constants, simple objects)
- ✅ **Share**: Expensive creation (database connections, API clients)
- ❌ **Don't share**: Mutable state that tests modify
- ❌ **Don't share**: Test-specific configurations (use parametrize instead)

**Fixture scope options:**
```python
@pytest.fixture(scope='function')  # Default: new instance per test
@pytest.fixture(scope='class')     # One instance per test class
@pytest.fixture(scope='module')    # One instance per test file
@pytest.fixture(scope='session')   # One instance for entire test run
```

**Reference**: See `tests/conftest.py` for project-wide fixtures like `temp_db_path`

---

# FILE SIZE & NAMING

## When to Split
- File exceeds 600 lines → MUST split

## Naming Conventions

```python
# Unit tests
test_<module>.py                # Single module
test_<module>_<feature>.py      # Feature within module

# Integration tests
test_<workflow>.py               # Complete workflow
```

### Test Classes
```python
TestClassName        # For 1:1 mapping
TestFeatureName      # For features
TestModuleErrors     # For errors
```

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

# WHAT NOT TO DO

### ❌ DON'T: Create one giant test file
If exceeds 600 lines, split by feature/responsibility.

### ❌ DON'T: Forget to test enums
Enum values stored in DB - changing breaks existing data.

### ❌ DON'T: Mix patterns randomly
Classes get 1:1, functions get feature grouping.

### ❌ DON'T: Use vague test names
`test_1()` → `test_store_news_with_duplicate_url_skips()`

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
- [ ] Updated `docs/Test_Catalog.md` (added/removed files, tests listed with one-line descriptions)

## When in Doubt
1. **Make it obvious** where to find/add tests
2. **Keep files small** enough to understand quickly
3. **Follow the pattern** for that type of module
4. **Ask yourself:** "Will someone new understand this in 6 months?"

---

# EXAMPLE PATTERNS REFERENCE

**Use these as templates when writing similar tests (see FOLLOW_SIMILAR_TESTS above)**

- **1:1 Class Mapping**: Source `data/providers/finnhub/client.py` → Test `tests/unit/data/providers/test_finnhub.py` has `TestFinnhubClient`
  - Copy for: Polygon providers, new data providers

- **Shared Behavior Tests (Repeated Behavior)**: Multiple providers → Shared behavior test parametrized by ProviderSpec
  - When: FinnhubNewsProvider and PolygonNewsProvider share same behavior (skip missing headline, parse valid article)
  - Use for: Avoiding duplicate tests across similar implementations

- **Feature-Based Functions**: Source `data/storage/storage_crud.py` → Tests split into `test_storage_news.py`, `test_storage_prices.py`
  - Copy for: New storage operations, utility modules

- **Integration Test**: `tests/integration/data/test_dedup_news.py`, `test_roundtrip_e2e.py`, `test_timezone_pipeline.py`
  - Copy for: New workflows, E2E validation

- **Retry Logic**: `tests/unit/utils/test_http.py::test_429_numeric_retry_after`
  - Copy for: HTTP clients, retry wrappers

