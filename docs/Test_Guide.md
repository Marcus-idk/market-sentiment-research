# Test Organization Guide

## Quick Decision Tree - WHERE DO I PUT MY TEST?

```
START HERE
    ↓
Is it a unit test or integration test?
    ├─ UNIT TEST → tests/unit/ (mirrors source structure)
    └─ INTEGRATION TEST → tests/integration/ (organized by feature)
        └─ STOP. Name it test_<workflow>.py, mark with @pytest.mark.integration

For UNIT TESTS, continue:
    ↓
What's in your source file?
    ├─ CLASSES ONLY → 1:1 mapping rule
    ├─ FUNCTIONS ONLY → Feature grouping rule  
    ├─ BOTH CLASSES AND FUNCTIONS → Hybrid rule
    └─ ABSTRACT BASE CLASSES → Contract test rule
```

## The Rules (with Examples)

### Rule 1: Classes Get 1:1 Mapping

**If your file has classes:**
```python
# data/providers/finnhub.py
class FinnhubClient:
    ...
class FinnhubNewsProvider:
    ...
```

**Your test must have:**
```python
# tests/unit/data/providers/test_finnhub.py
class TestFinnhubClient:
    ...
class TestFinnhubNewsProvider:
    ...
```

✅ **GOOD:** Easy to find - "Where's test for FinnhubClient? Oh, TestFinnhubClient!"  
❌ **BAD:** Random names like TestFinnhubStuff or TestNewsFeatures

### Rule 2: Functions Get Feature Groups

**If your file has only functions:**
```python
# data/storage.py
def store_news_items():
def get_news_since():
def store_price_data():
def get_price_data_since():
# ... 25 functions total
```

**Split tests by FEATURE into multiple files:**
```python
# tests/unit/data/test_storage_news.py
class TestNewsStorage:
    def test_store_news_items_valid():
    def test_get_news_since_returns_sorted():

# tests/unit/data/test_storage_prices.py  
class TestPriceStorage:
    def test_store_price_data_valid():
    def test_get_price_data_since_filters_correctly():
```

✅ **GOOD:** Small files (~400 lines max), organized by what they do  
❌ **BAD:** One giant 1200-line file with 12 classes

### Rule 3: Mixed Files Get Both

**If your file has both classes AND functions:**
```python
# utils/helpers.py (hypothetical)
class CacheManager:
    ...
def normalize_string():
def validate_input():
```

**Your tests:**
```python
# tests/unit/utils/test_helpers.py
class TestCacheManager:  # 1:1 for the class
    ...

# tests/unit/utils/test_helpers_functions.py
class TestStringHelpers:  # or just use plain functions
    def test_normalize_string():
    def test_validate_input():
```

### Rule 4: ABCs Get Contract Tests

**If your file has abstract base classes:**
```python
# data/base.py
class DataSource(ABC):
    @abstractmethod
    def fetch():
```

**Your test uses behavior/contract style:**
```python
# tests/unit/data/test_base.py (or test_base_contracts.py)
class TestDataSourceContract:
    def test_all_implementations_have_fetch():
    def test_fetch_returns_expected_type():
```

✅ **GOOD:** Tests the contract, not forcing 1:1  
❌ **BAD:** TestDataSource, TestNewsDataSource (meaningless for ABCs)

### Rule 5: Enums Need Value Lock Tests

**If you have enums:**
```python
# data/models.py
class Session(Enum):
    REG = "REG"
    PRE = "PRE"
    POST = "POST"
    CLOSED = "CLOSED"
```

**Add a simple test:**
```python
# tests/unit/data/test_models.py (or test_models_enums.py)
def test_enum_values_unchanged():
    # These values are in the database - MUST NOT CHANGE
    assert Session.REG.value == "REG"
    assert Session.PRE.value == "PRE"
    assert Session.POST.value == "POST"
    assert Session.CLOSED.value == "CLOSED"
```

✅ **GOOD:** Prevents accidental breaking changes  
❌ **BAD:** No test at all (someone changes "REG" to "REGULAR" and breaks the DB)

## File Size Limits

- **Target:** ~400 lines per test file
- **Maximum:** ~600 lines
- **Test class:** ~200-250 lines max

**When to split:** If you're scrolling too much to find things, SPLIT IT!

## Naming Conventions

### Test Files
- Unit tests: `test_<module>.py` or `test_<module>_<feature>.py`
- Integration tests: `test_<workflow>.py`

### Test Classes
- For 1:1 mapping: `TestClassName`
- For features: `TestFeatureName`
- For errors: `TestModuleErrors`

### Test Methods
- Be descriptive: `test_store_news_with_duplicate_url_skips`
- NOT vague: `test_store_1` or `test_news`

## What NOT To Do

### ❌ DON'T: Create one giant test file
If your test file exceeds 600 lines, split it by feature or responsibility.

### ❌ DON'T: Forget to test enums
Enum values are stored in the database - changing them breaks existing data.

### ❌ DON'T: Mix patterns randomly
Stick to the rules above - classes get 1:1 mapping, functions get feature grouping.

### ❌ DON'T: Use vague test names
```python
# Bad:
def test_1():
def test_stuff():

# Good:
def test_store_news_with_duplicate_url_skips():
def test_price_validation_rejects_negative_values():
```

## Integration Tests

**Different rules - organize by FEATURE/WORKFLOW, not source structure:**

```
tests/integration/
├── data/
│   ├── test_news_deduplication.py  (workflow: dedup logic)
│   ├── test_price_updates.py       (workflow: price updates)
│   └── test_roundtrip_e2e.py       (workflow: full data cycle)
└── llm/
    └── test_provider_responses.py   (workflow: LLM interactions)
```

- Always mark with `@pytest.mark.integration`
- Can use real databases, APIs (in integration only!)
- Test complete workflows, not individual functions

## Quick Checklist for New Tests

- [ ] Is it in the right location? (Check decision tree)
- [ ] Does it follow the pattern for that module type?
- [ ] Is the test file < 600 lines? (split if not)
- [ ] Are test names descriptive?
- [ ] Do enums have value lock tests?
- [ ] Are integration tests marked correctly?

## Example Patterns

### ✅ GOOD: 1:1 Class Mapping
```python
# Source: data/providers/finnhub.py has FinnhubClient class
# Test: tests/unit/data/providers/test_finnhub.py has TestFinnhubClient class
```

### ✅ GOOD: Feature-Based Function Tests
```python
# Source: data/storage.py has many functions
# Tests: Split into test_storage_news.py, test_storage_prices.py, etc.
```

### ✅ GOOD: Integration Test Organization
```python
# Tests organized by workflow, not source structure:
# test_dedup_news.py, test_roundtrip_e2e.py, test_timezone_pipeline.py
```

## When in Doubt

1. **Make it obvious** where to find/add tests
2. **Keep files small** enough to understand quickly
3. **Follow the pattern** for that type of module
4. **Ask yourself:** "Will someone new understand this in 6 months?"
