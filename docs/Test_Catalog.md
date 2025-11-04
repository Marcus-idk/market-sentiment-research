# Test Catalog — Complete Test Inventory

This document enumerates all tests under `tests/` and what they cover.
Keep it human-scannable and low-churn; do not duplicate this inventory in other docs.

## Rules to Follow When Updating This
- Keep this as the single source for the test inventory.
- Update when a test file is added/removed, or when tests are added/removed/renamed.
- For each file, include: Purpose, Tags (optional), key Fixtures (optional), Tests, Notes (optional).
- List ALL test functions with one-line descriptions of what they validate.
- Structure: File → Class (if exists) → Test functions. If no classes, list tests directly under file.
- Order: Files mirror the `tests/` tree structure. Within each file, list tests in the order they appear.
- Use tags consistently (see Tag Legend). Note env vars/time freezing only if relevant.
- Wrap all file paths and test function names in backticks so they’re easy to scan (e.g., `tests/unit/.../test_x.py`, `test_function_name`).

## Tag Legend
- [network] — Performs real HTTP calls; requires network and API keys.
- [shared] — Shared behavior suite applied across implementations.
- [async] — Module-level asyncio usage in this file.

## Entry Template (Use for Each Test File)

### `tests/…/test_xxx.py`
- Purpose: one-line description of what the file validates
- Tags: [network?] [shared?] [async?]
- Fixtures: key shared fixtures used (file-level), if any
- Tests:

  **TestClassName** (if file has classes; otherwise list tests directly)
  - `test_function_name` - One-line description of what this test validates
  - `test_another_function` - Another one-line description

  **AnotherTestClass** (if multiple classes)
  - `test_in_second_class` - Description

  OR (if no classes):
  - `test_function_name` - One-line description of what this test validates
  - `test_another_function` - Another one-line description

- Notes: optional caveats (time frozen/current, env vars, flakiness, deprecations)

---

The detailed inventory starts below this line (to be populated and maintained).

### `tests/integration/data/providers/test_finnhub_live.py`
- Purpose: Verify Finnhub API works as expected with real data
- Tags: [network] [async]
- Tests:
  - `test_live_quote_fetch` - Fetches live quotes
  - `test_live_news_fetch` - Fetches live news
  - `test_live_multiple_symbols` - Multiple symbols fetch
  - `test_live_error_handling` - Handles invalid symbol gracefully
- Notes: Requires FINNHUB_API_KEY; network access

### `tests/integration/data/providers/test_polygon_live.py`
- Purpose: Verify Polygon API works as expected with real data
- Tags: [network] [async]
- Tests:
  - `test_live_news_fetch` - Fetches live news
  - `test_live_multiple_symbols` - Multiple symbols fetch
  - `test_live_error_handling` - Handles invalid symbol gracefully
- Notes: Requires POLYGON_API_KEY; network access

### `tests/integration/data/test_decimal_precision.py`
- Purpose: Decimal precision across pipeline
- Tests:
  **TestDecimalPrecision**
  - `test_financial_precision_preservation` - Preserves precision E2E

### `tests/integration/data/test_dedup_news.py`
- Purpose: Cross-provider deduplication
- Tests:
  **TestNewsDeduplication**
  - `test_cross_provider_deduplication` - Deduplicates across sources

### `tests/integration/data/test_roundtrip_e2e.py`
- Purpose: End-to-end data pipeline roundtrip
- Tests:
  **TestDataRoundtrip**
  - `test_complete_data_roundtrip` - Full model roundtrip
  - `test_cross_model_data_consistency` - Cross-model consistency
  - `test_upsert_invariants` - Upsert invariants across models
  - `test_duplicate_price_prevention` - Prevents duplicate price rows

### `tests/integration/data/test_schema_constraints.py`
- Purpose: Schema constraint enforcement under workflow
- Tests:
  **TestSchemaConstraints**
  - `test_transaction_rollback_on_constraint_violation` - Rolls back on violations

### `tests/integration/data/test_timezone_pipeline.py`
- Purpose: UTC/timezone normalization across pipeline
- Tests:
  **TestTimezonePipeline**
  - `test_timezone_consistency` - UTC consistency across pipeline

### `tests/integration/data/test_wal_sqlite.py`
- Purpose: SQLite WAL mode and concurrency behavior
- Tests:
  **TestWALSqlite**
  - `test_wal_mode_functionality` - WAL mode enabled and functional
  - `test_concurrent_operations_with_wal` - Concurrent read/write behavior

### `tests/integration/llm/shared/test_llm_code_tools_shared.py`
- Purpose: LLM code tools parity across providers
- Tags: [shared] [network] [async]
- Tests:
  - `test_code_tools_enabled_matches_expected_digest` - Digest matches when tools enabled
  - `test_code_tools_disabled_does_not_match_digest` - Digest does not match when disabled
- Notes: Requires LLM API keys; network

### `tests/integration/llm/shared/test_llm_connection_shared.py`
- Purpose: LLM connectivity and basic generation
- Tags: [shared] [network] [async]
- Tests:
  - `test_provider_validates_connection` - validate_connection passes
  - `test_provider_generates_basic_response` - Generates non-empty response
- Notes: Requires LLM API keys; network

### `tests/integration/llm/shared/test_llm_web_search_shared.py`
- Purpose: LLM web search tooling parity
- Tags: [shared] [network] [async]
- Tests:
  - `test_web_search_enabled_returns_expected_title` - Finds expected title when enabled
  - `test_web_search_disabled_does_not_find_title` - Does not find title when disabled
- Notes: Requires network; Wikipedia access

### `tests/unit/analysis/test_news_classifier.py`
- Purpose: News classification stub behavior
- Tests:
  - `test_classify_returns_empty_list_for_any_input` - Stub returns empty list for any entries
  - `test_classify_handles_empty_list` - Handles empty input list

### `tests/unit/analysis/test_urgency_detector.py`
- Purpose: Urgency detector stub behavior
- Tests:
  - `test_detect_urgency_returns_empty_list` - Returns empty urgent list
  - `test_detect_urgency_handles_empty_list` - Handles empty input list
  - `test_detect_urgency_extracts_text_from_headline_and_content` - Extracts text safely from headline/content

### `tests/unit/config/shared/test_settings_shared.py`
- Purpose: Unified env loading/validation across Finnhub, Polygon, OpenAI, Gemini
- Tests:
  **TestSettingsShared**
  - `test_from_env_success` - Loads when key set
  - `test_from_env_missing_key` - Raises on missing key
  - `test_from_env_empty_key` - Raises on empty key
  - `test_from_env_whitespace_key` - Raises on whitespace key
  - `test_from_env_strips_whitespace` - Strips whitespace
  - `test_from_env_custom_env_dict` - Accepts custom env dict

### `tests/unit/config/llm/test_gemini.py`
- Purpose: Gemini-specific settings (placeholder; covered by shared tests)
- Tests:
  - (none)
- Notes: Common checks live in shared test suite

### `tests/unit/config/llm/test_openai.py`
- Purpose: OpenAI-specific settings (placeholder; covered by shared tests)
- Tests:
  - (none)
- Notes: Common checks live in shared test suite

### `tests/unit/config/providers/test_finnhub_settings.py`
- Purpose: Finnhub-specific settings (placeholder; covered by shared tests)
- Tests:
  - (none)
- Notes: Common checks live in shared test suite

### `tests/unit/config/providers/test_polygon_settings.py`
- Purpose: Polygon-specific settings (placeholder; covered by shared tests)
- Tests:
  - (none)
- Notes: Common checks live in shared test suite

### `tests/unit/config/test_config_retry.py`
- Purpose: Retry configuration dataclasses and defaults
- Tests:
  **TestLLMRetryConfig**
  - `test_custom_values` - Accepts custom values
  - `test_partial_custom_values` - Mix of custom and defaults
  - `test_immutability` - Frozen dataclass enforces immutability
  - `test_default_instance` - DEFAULT_LLM_RETRY values
  - `test_default_instance_immutable` - DEFAULT_LLM_RETRY is immutable
  **TestDataRetryConfig**
  - `test_custom_values` - Accepts custom values
  - `test_partial_custom_values` - Mix of custom and defaults
  - `test_immutability` - Frozen dataclass enforces immutability
  - `test_default_instance` - DEFAULT_DATA_RETRY values
  - `test_default_instance_immutable` - DEFAULT_DATA_RETRY is immutable
  **TestRetryBusinessRules**
  - `test_different_timeouts` - LLM vs Data default timeout rule

### `tests/unit/data/providers/shared/test_client_shared.py`
- Purpose: Provider HTTP client shared behaviors
- Tags: [shared] [async]
- Tests:
  **TestClientShared**
  - `test_get_builds_url_and_injects_auth` - Builds URL and injects auth
  - `test_get_handles_none_params` - Handles None params
  - `test_validate_connection_success` - validate_connection returns True
  - `test_validate_connection_failure_returns_false` - validate_connection returns False on error
  - `test_get_respects_custom_base_url_override` - Honors custom base_url

### `tests/unit/data/providers/shared/test_news_company_shared.py`
- Purpose: Company news providers shared behaviors
- Tags: [shared] [async]
- Tests:
  **TestNewsCompanyShared**
  - `test_validate_connection_success` - validate_connection returns True
  - `test_validate_connection_failure` - validate_connection raises on error
  - `test_parses_valid_article` - Parses valid article
  - `test_skips_missing_headline` - Skips blank headline
  - `test_skips_missing_url` - Skips blank URL
  - `test_skips_invalid_timestamp` - Skips invalid timestamp
  - `test_filters_articles_with_buffer` - Applies 2-minute buffer
  - `test_date_window_params_with_since` - Adds correct date/ISO params with since
  - `test_date_window_params_without_since` - Adds correct date/ISO params without since
  - `test_symbol_normalization_uppercases` - Uppercases symbol list
  - `test_summary_copied_to_content` - Copies summary to content
  - `test_per_symbol_error_isolation` - Isolates errors per symbol
  - `test_structural_error_raises` - Malformed response raises DataSourceError
  - `test_empty_response_returns_empty_list` - Empty response returns []

### `tests/unit/data/providers/shared/test_news_macro_shared.py`
- Purpose: Macro news providers shared behaviors
- Tags: [shared] [async]
- Tests:
  **TestNewsMacroShared**
  - `test_validate_connection_success` - validate_connection returns True
  - `test_validate_connection_failure` - validate_connection raises on error
  - `test_maps_related_symbols` - Maps related symbols to watchlist
  - `test_falls_back_to_market_when_no_related` - Falls back to market when none related
  - `test_filters_buffer_time_when_bootstrap` - Applies bootstrap buffer
  - `test_invalid_articles_are_skipped` - Skips invalid articles
  - `test_structural_error_raises` - Raises on malformed response type
  - `test_empty_watchlist_falls_back_to_market` - Empty watchlist => market

### `tests/unit/data/providers/shared/test_prices_shared.py`
- Purpose: Price providers shared behaviors
- Tags: [shared] [async]
- Tests:
  **TestPricesShared**
  - `test_validate_connection_success` - validate_connection returns True
  - `test_validate_connection_failure` - validate_connection raises on error
  - `test_decimal_conversion` - Converts price to Decimal
  - `test_classifies_session` - Classifies market session
  - `test_rejects_negative_price` - Rejects negative price
  - `test_rejects_zero_price` - Rejects zero price
  - `test_rejects_string_price` - Rejects non-numeric price
  - `test_rejects_missing_price_field` - Skips missing price field
  - `test_timestamp_fallback_when_missing` - Uses now when timestamp missing
  - `test_timestamp_fallback_when_invalid` - Uses now when timestamp invalid
  - `test_error_isolation_per_symbol` - Isolates errors per symbol
  - `test_non_dict_quote_skipped` - Skips non-dict quotes

### `tests/unit/data/providers/test_finnhub_news.py`
- Purpose: Finnhub company news specifics (beyond shared tests)
- Tags: [async]
- Tests:
  **TestFinnhubNewsProviderSpecific**
  - `test_fetch_incremental_with_no_symbols_returns_empty_list` - Empty symbols => empty list

### `tests/unit/data/providers/test_finnhub_macro.py`
- Purpose: Finnhub macro news specifics (beyond shared tests)
- Tags: [async]
- Fixtures: macro_provider
- Tests:
  **TestFinnhubMacroProviderSpecific**
  - `test_fetch_incremental_includes_min_id_param` - Includes minId param
  - `test_last_fetched_max_id_advances_only_on_newer_ids` - Tracks and resets last_fetched_max_id

### `tests/unit/data/providers/test_finnhub_prices.py`
- Purpose: Finnhub price specifics (beyond shared tests)
- Tags: [async]
- Tests:
  **TestFinnhubPriceProviderSpecific**
  - `test_fetch_incremental_with_no_symbols_returns_empty_list` - Empty symbols => empty list

### `tests/unit/data/providers/test_polygon_news.py`
- Purpose: Polygon company news specifics (beyond shared tests)
- Tags: [async]
- Tests:
  **TestPolygonNewsProvider**
  - `test_fetch_incremental_handles_pagination` - Handles next_url pagination
  - `test_extract_cursor_from_next_url` - Extracts cursor from next_url

### `tests/unit/data/providers/test_polygon_macro_news.py`
- Purpose: Polygon macro news specifics (beyond shared tests)
- Tags: [async]
- Tests:
  **TestPolygonMacroNewsProvider**
  - `test_fetch_incremental_handles_pagination` - Handles next_url pagination
  - `test_extract_cursor_from_next_url` - Extracts cursor from next_url

### `tests/unit/data/schema/test_schema_confidence_and_json.py`
- Purpose: JSON fields and confidence constraints
- Tests:
  **TestConfidenceScoreRange**
  - `test_confidence_score_boundaries` - Enforces bounds
  - `test_confidence_score_out_of_range` - Rejects out-of-range
  **TestJSONConstraints**
  - `test_json_valid_constraint` - Valid JSON object
  - `test_json_type_object_constraint` - Rejects non-object

### `tests/unit/data/schema/test_schema_defaults_and_structure.py`
- Purpose: Schema defaults and structure
- Tests:
  **TestDefaultValues**
  - `test_session_default_reg` - Defaults session to REG
  - `test_timestamp_defaults` - Default timestamps
  - `test_news_symbols_timestamp_default` - news_symbols created_at default
  **TestTableStructure**
  - `test_without_rowid_optimization` - WITHOUT ROWID optimization

### `tests/unit/data/schema/test_schema_enums.py`
- Purpose: Enum value locks and constraints
- Tests:
  **TestEnumValueLocks**
  - `test_session_enum_values_unchanged` - Locks Session values
  - `test_stance_enum_values_unchanged` - Locks Stance values
  - `test_analysis_type_enum_values_unchanged` - Locks AnalysisType values
  - `test_news_type_enum_values_unchanged` - Locks NewsType values
  - `test_urgency_enum_values_unchanged` - Locks Urgency values
  **TestEnumConstraints**
  - `test_session_enum_values` - Enforces session constraint
  - `test_stance_enum_values` - Enforces stance constraint
  - `test_analysis_type_enum_values` - Enforces analysis_type constraint
  - `test_news_type_enum_values` - Enforces news_type constraint
  - `test_news_symbols_is_important_constraint` - `news_symbols.is_important` allows NULL/0/1 only

### `tests/unit/data/schema/test_schema_financial_values.py`
- Purpose: Decimal/numeric constraints
- Tests:
  **TestFinancialConstraints**
  - `test_price_must_be_positive` - Positive prices only
  - `test_price_boundary_values` - Boundary values (very small/large, invalid text)
  - `test_holdings_quantity_positive` - Positive holdings quantity
  - `test_holdings_break_even_positive` - break_even_price > 0
  - `test_holdings_total_cost_positive` - total_cost > 0
  **TestVolumeConstraints**
  - `test_volume_non_negative` - Volume non-negative
  - `test_volume_null_allowed` - Volume can be NULL

### `tests/unit/data/schema/test_schema_last_seen_keys.py`
- Purpose: Watermark key presence/constraints
- Tests:
  **TestLastSeenKeyConstraint**
  - `test_last_seen_key_accepts_macro_news_min_id` - Validates allowed/invalid keys

### `tests/unit/data/schema/test_schema_not_null.py`
- Purpose: NOT NULL constraint coverage
- Tests:
  **TestNotNullConstraints**
  - `test_news_items_required_fields` - News required fields
  - `test_news_symbols_required_fields` - news_symbols required fields
  - `test_price_data_required_fields` - Price required fields
  - `test_analysis_results_required_fields` - Analysis required fields
  - `test_holdings_required_fields` - Holdings required fields

### `tests/unit/data/schema/test_schema_primary_keys.py`
- Purpose: Primary key constraints
- Tests:
  **TestPrimaryKeyConstraints**
  - `test_news_items_primary_key` - url primary key
  - `test_news_symbols_composite_key` - (url, symbol) composite key
  - `test_price_data_composite_key` - (symbol, timestamp_iso) composite key
  - `test_analysis_results_composite_key` - (symbol, analysis_type) composite key
  - `test_holdings_single_key` - symbol primary key

### `tests/unit/data/storage/test_storage_analysis.py`
- Purpose: Analysis result persistence
- Tests:
  **TestAnalysisResultUpsert**
  - `test_upsert_analysis_conflict_resolution` - Upsert conflict handling
  - `test_upsert_analysis_auto_created_at` - Auto created_at behavior

### `tests/unit/data/storage/test_storage_cutoff.py`
- Purpose: Time-based cutoff handling
- Tests:
  **TestCutoffQueries**
  - `test_get_news_before_cutoff_filtering` - News before cutoff filtering
  - `test_get_news_before_boundary_conditions` - News cutoff boundary cases
  - `test_get_prices_before_cutoff_filtering` - Prices before cutoff filtering
  - `test_get_prices_before_boundary_conditions` - Prices cutoff boundary cases

### `tests/unit/data/storage/test_storage_db.py`
- Purpose: DB init and PRAGMAs
- Tests:
  **TestDatabaseInitialization**
  - `test_init_database_creates_schema` - Creates schema
  - `test_schema_file_not_found_raises_error` - Raises on missing schema file
  - `test_wal_mode_enabled` - WAL enabled
  - `test_foreign_keys_enabled_by_default` - Foreign keys enabled

### `tests/unit/data/storage/test_storage_db_context.py`
- Purpose: Cursor context manager behavior
- Tests:
  **TestCursorContext**
  - `test_cursor_context_commit_true_commits_on_success` - Commits on success
  - `test_cursor_context_commit_false_no_commit` - No commit when commit=False
  - `test_cursor_context_rollback_on_exception` - Rollback on Exception
  - `test_cursor_context_rollback_on_base_exception` - Rollback on BaseException
  - `test_cursor_context_sets_row_factory` - Sets sqlite3.Row factory
  - `test_cursor_context_cleanup_on_cursor_error` - Cleanup on cursor error
  - `test_cursor_context_cleanup_in_finally` - Always closes connection

### `tests/unit/data/storage/test_storage_errors.py`
- Purpose: Error handling scenarios
- Tests:
  **TestErrorHandling**
  - `test_database_operations_with_nonexistent_db` - Nonexistent DB operations
  - `test_query_operations_with_empty_database` - Empty DB queries

### `tests/unit/data/storage/test_storage_holdings.py`
- Purpose: Holdings persistence and updates
- Tests:
  **TestHoldingsUpsert**
  - `test_upsert_holdings_timestamp_handling` - Preserve created_at, update updated_at
  - `test_upsert_holdings_auto_timestamps` - Auto-generate timestamps

### `tests/unit/data/storage/test_storage_last_seen.py`
- Purpose: Watermark storage behavior
- Tests:
  **TestLastSeenState**
  - `test_basic_roundtrip_set_get` - Basic set/get functionality
  - `test_replace_existing_key` - INSERT OR REPLACE overwrites existing keys
  - `test_unknown_key_returns_none` - Non-existent keys return None
  - `test_unicode_safety` - Unicode handling in values
  - `test_key_constraint_enforcement` - CHECK constraint rejects invalid keys
  **TestLastNewsTime**
  - `test_roundtrip_aware_timestamp` - UTC-aware datetime roundtrip
  - `test_naive_timestamp_treated_as_utc` - Naive datetime treated as UTC
  - `test_overwrite_behavior` - Last write wins, no monotonic enforcement
  - `test_missing_key_returns_none` - Missing news_since_iso key returns None
  **TestLastMacroMinId**
  - `test_macro_min_id_roundtrip_int` - Integer roundtrip
  - `test_macro_min_id_missing_returns_none` - Missing returns None
  - `test_macro_min_id_overwrite_and_nonint_value_returns_none` - Overwrite/non-int returns None

### `tests/unit/data/storage/test_storage_llm_batch.py`
- Purpose: LLM batch commit flow
- Tests:
  **TestBatchOperations**
  - `test_commit_llm_batch_atomic_transaction` - Atomic delete ≤ cutoff, set watermark
  - `test_commit_llm_batch_empty_database` - No-op on empty DB, set watermark
  - `test_commit_llm_batch_boundary_conditions` - Boundary timestamp behavior (≤ cutoff)
  - `test_commit_llm_batch_idempotency` - Idempotent repeated calls

### `tests/unit/data/storage/test_storage_news.py`
- Purpose: News storage and symbol links
- Tests:
  **TestNewsItemStorage**
  - `test_store_news_deduplication_insert_or_ignore` - Dedup via normalized URL
  - `test_store_news_empty_list_no_error` - Empty list no-op
  **TestNewsSymbolsStorage**
  - `test_store_and_get_news_symbols` - Stores and retrieves news_symbols links
  - `test_get_news_symbols_filters_by_symbol` - get facade filters by symbol
  - `test_news_symbols_cascade_on_news_deletion` - Cascades on news delete
  - `test_store_news_symbols_conflict_updates_is_important` - Conflict update flips importance flag

### `tests/unit/data/storage/test_storage_prices.py`
- Purpose: Price storage validation
- Tests:
  **TestPriceDataStorage**
  - `test_store_price_data_type_conversions` - Decimal/enum to storage types
  - `test_store_price_data_deduplication` - Dedup by (symbol, timestamp)

### `tests/unit/data/storage/test_storage_queries.py`
- Purpose: Query helper coverage
- Tests:
  **TestQueryOperations**
  - `test_get_news_since_timestamp_filtering` - Since filter and ordering
  - `test_get_price_data_since_ordering` - Price ordering
  - `test_get_all_holdings_ordering` - Holdings symbol ordering
  - `test_get_analysis_results_symbol_filtering` - Analysis results symbol filter

### `tests/unit/data/storage/test_storage_types.py`
- Purpose: Type conversions
- Tests:
  **TestTypeConversions**
  - `test_datetime_to_iso_format_utc_aware` - UTC-aware ISO format
  - `test_datetime_to_iso_format_naive` - Naive treated as UTC
  - `test_datetime_to_iso_strips_microseconds` - Strip microseconds
  - `test_decimal_to_text_precision_preservation` - Decimal precision preserved

### `tests/unit/data/storage/test_storage_url.py`
- Purpose: URL normalization helpers
- Tests:
  **TestURLNormalization**
  - `test_normalize_url_strips_tracking_parameters` - Strips tracking params
  - `test_normalize_url_preserves_essential_parameters` - Preserves essential params
  - `test_normalize_url_canonical_ordering` - Canonical ordering
  - `test_normalize_url_mixed_tracking_and_essential` - Mixed cases
  - `test_normalize_url_lowercases_hostname` - Lowercases hostname

### `tests/unit/data/storage/test_storage_utils_parsing.py`
- Purpose: ISO/RFC3339 parsing and row mappers
- Tests:
  **TestIsoParsingHelpers**
  - `test_iso_to_datetime_parses_z_suffix` - Parses Z-suffix ISO
  - `test_iso_to_datetime_preserves_offset` - Preserves +00:00 offset
  - `test_parse_rfc3339_handles_naive_as_utc` - Naive treated as UTC
  - `test_parse_rfc3339_raises_for_non_string` - Type error for non-string
  - `test_parse_rfc3339_invalid_format_raises` - Invalid format raises
  **TestRowMappers**
  - `test_row_to_news_item_maps_fields_and_type` - Map row → NewsItem (includes news_type)
  - `test_row_to_news_symbol_maps_fields_and_nullable_is_important` - Nullable importance handled
  - `test_row_to_news_entry_maps_joined_row` - Joined row → NewsEntry
  - `test_row_to_price_data_maps_decimal_and_session` - Decimal and session mapping
  - `test_row_to_analysis_result_builds_model` - Build AnalysisResult
  - `test_row_to_holdings_parses_decimals` - Parse Decimal fields

### `tests/unit/data/test_data_base.py`
- Purpose: Data provider base classes and exceptions
- Tests:
  **TestDataSourceContract**
  - `test_source_name_none_raises` - Rejects None source name
  - `test_source_name_must_be_string` - Rejects non-string types
  - `test_source_name_cannot_be_empty` - Rejects empty/whitespace
  - `test_source_name_length_limit` - Rejects >100 chars
  - `test_source_name_normalization` - Trims and preserves valid names
  - `test_datasource_is_abstract` - Cannot instantiate ABC directly
  **TestNewsDataSourceContract**
  - `test_requires_fetch_incremental` - Enforces fetch_incremental implementation
  - `test_concrete_implementation_satisfies_contract` - Concrete subclass works
  **TestPriceDataSourceContract**
  - `test_requires_fetch_incremental` - Enforces fetch_incremental implementation
  - `test_concrete_implementation_satisfies_contract` - Concrete subclass works
  **TestDataSourceErrorContract**
  - `test_exception_inheritance` - DataSourceError hierarchy

### `tests/unit/data/test_models.py`
- Purpose: Dataclasses and enums validation
- Tests:
  **TestNewsItem**
  - `test_newsitem_valid_creation` - Valid creation
  - `test_newsitem_url_validation` - URL validation
  - `test_newsitem_empty_field_validation` - Empty field rejection
  - `test_newsitem_news_type_variants` - Accepts enum or exact string values
  - `test_newsitem_timezone_normalization` - UTC normalization
  **TestNewsEntry**
  - `test_newsentry_symbol_uppercasing_and_passthrough` - Symbol uppercased; article passthrough
  - `test_newsentry_is_important_accepts_bool_or_none` - Bool/None accepted
  - `test_newsentry_requires_non_empty_symbol` - Rejects empty symbol
  - `test_newsentry_invalid_is_important_value` - Rejects non-bool importance
  **TestNewsSymbol**
  - `test_newssymbol_valid_creation` - Valid link object
  - `test_newssymbol_importance_bool_conversion` - Bool conversion
  - `test_newssymbol_invalid_inputs_raise` - URL/symbol/importance validation
  **TestPriceData**
  - `test_pricedata_symbol_uppercasing` - Symbol uppercased
  - `test_pricedata_price_must_be_positive` - Positive price only
  - `test_pricedata_volume_validation` - Volume validation
  - `test_pricedata_session_enum_validation` - Session enum validation
  - `test_pricedata_decimal_precision` - Decimal precision
  - `test_pricedata_timezone_normalization` - UTC normalization
  - `test_pricedata_symbol_validation` - Symbol validation
  **TestAnalysisResult**
  - `test_analysisresult_symbol_uppercasing` - Symbol uppercased
  - `test_analysisresult_json_validation` - JSON validation
  - `test_analysisresult_confidence_range` - Confidence range
  - `test_analysisresult_enum_validation` - Enum validation
  - `test_analysisresult_timezone_normalization` - UTC normalization
  - `test_analysisresult_symbol_validation` - Symbol validation
  - `test_analysisresult_empty_string_validation` - Empty string rejection
  **TestHoldings**
  - `test_holdings_symbol_uppercasing` - Symbol uppercased
  - `test_holdings_financial_values_positive` - Positive financial values
  - `test_holdings_decimal_precision` - Decimal precision
  - `test_holdings_timezone_normalization` - UTC normalization
  - `test_holdings_symbol_validation` - Symbol validation
  - `test_holdings_notes_trimming` - Notes trimming

### `tests/unit/llm/test_llm_base.py`
- Purpose: LLM provider base class contracts
- Tests:
  **TestLLMProviderInitialization**
  - `test_llmprovider_stores_config_kwargs` - Stores config kwargs
  **TestAbstractMethodEnforcement**
  - `test_llmprovider_cannot_instantiate` - Abstract cannot instantiate
  - `test_llmprovider_requires_generate` - Requires generate()
  - `test_llmprovider_requires_validate_connection` - Requires validate_connection()
  - `test_concrete_implementation_works` - Concrete subclass works
  **TestExceptionHierarchy**
  - `test_llm_error_inheritance` - Exception inheritance

### `tests/unit/llm/providers/test_openai_provider.py`
- Purpose: Unit coverage for OpenAI provider argument passing and error mapping
- Tags: [async]
- Fixtures: `monkeypatch`
- Tests:
  **TestOpenAIProvider**
  - `test_generate_passes_expected_args` - Forwards args (model, input, temp, reasoning, tools, tool_choice)
  - `test_generate_respects_custom_reasoning` - Uses custom reasoning; omits temperature when None
  - `test_classify_rate_limit_with_retry_after` - Rate limit uses Retry-After header
  - `test_classify_rate_limit_without_retry_after` - Rate limit without Retry-After
  - `test_classify_retryable_errors` - Timeout/connection/conflict mapped retryable
  - `test_classify_api_status_retryable` - 5xx mapped retryable
  - `test_classify_api_status_rate_limit` - 429 mapped retryable with Retry-After
  - `test_classify_api_status_non_retryable` - 400 mapped non-retryable with code
  - `test_classify_non_retryable_openai_errors` - Auth/perm/bad request/not found/422 mapped non-retryable
  - `test_classify_falls_back_to_llm_error` - Unexpected exceptions map to LLMError
  - `test_validate_connection_failure` - Returns False on models.list failure

### `tests/unit/llm/providers/test_gemini_provider.py`
- Purpose: Unit coverage for Gemini provider tool config, thinking config, and error mapping
- Tags: [async]
- Fixtures: `monkeypatch`
- Tests:
  **TestGeminiProvider**
  - `test_generate_maps_tool_choice` - Maps tool_choice to NONE/AUTO/ANY modes
  - `test_generate_requires_tools_for_any` - Enforces tools when tool_choice="any"
  - `test_generate_uses_default_thinking` - Applies default thinking budget
  - `test_generate_uses_custom_thinking` - Applies custom thinking config
  - `test_generate_raises_when_no_candidates` - Raises when response has no candidates
  - `test_generate_combines_text_and_code_outputs` - Concatenates text and code outputs
  - `test_generate_handles_none_code_output` - Treats None code output as empty
  - `test_validate_connection_failure` - Returns False on models.list failure
  - `test_classify_server_error` - ServerError mapped retryable
  - `test_classify_api_error_codes` - APIError codes mapped retryable/non-retryable
  - `test_classify_api_error_rate_limit_uses_retry_after` - Honors Retry-After on 429
  - `test_classify_client_error` - ClientError mapped non-retryable
  - `test_classify_timeout_message` - Timeout message mapped retryable
  - `test_classify_connection_message` - Connection message mapped retryable
  - `test_classify_unexpected_error` - Fallback maps to LLMError

### `tests/unit/utils/test_http.py`
- Purpose: HTTP retry helper behaviors
- Tags: [async]
- Tests:
  **TestGetJsonWithRetry**
  - `test_200_ok_valid_json` - 200 OK returns JSON
  - `test_200_ok_invalid_json` - Invalid JSON raises without retry
  - `test_204_no_content` - 204 returns None
  - `test_401_403_auth_errors` - Auth errors raise without retry
  - `test_other_4xx_errors` - Other 4xx raise without retry
  - `test_429_numeric_retry_after` - 429 respects numeric Retry-After
  - `test_429_http_date_retry_after` - 429 respects HTTP-date Retry-After
  - `test_5xx_server_errors` - Retries on 5xx
  - `test_5xx_max_retries_exhausted` - Surfaces last error after retries
  - `test_timeout_exception` - Retries on TimeoutException
  - `test_transport_error` - Retries on TransportError
  - `test_query_params_passed_through` - Passes query params
  - `test_timeout_arg_is_forwarded` - Forwards timeout arg
  - `test_unexpected_status_raises` - Raises on unexpected status

### `tests/unit/utils/test_market_sessions.py`
- Purpose: US market session classification
- Tests:
  **TestClassifyUsSession**
  - `test_core_windows` - EDT/EST core windows
  - `test_exact_boundaries_and_precision` - Boundary precision
  - `test_dst_transitions` - DST transitions
  - `test_weekends_holidays_early_closes` - Weekends/holidays/early closes
  - `test_input_tz_handling` - Naive/ET/UTC handling
  - `test_same_utc_time_diff_seasons` - Same UTC, different seasons
  - `test_close_time_lookup_failure_falls_back_to_16_et_and_logs_warning` - Fallback to 16:00 ET

### `tests/unit/utils/test_retry.py`
- Purpose: Generic retry utilities
- Tags: [async]
- Tests:
  **TestParseRetryAfter**
  - `test_numeric_seconds` - Parses numeric seconds
  - `test_numeric_negative_floored` - Floors negatives to 0
  - `test_http_date_future` - Parses future HTTP-date
  - `test_http_date_past` - Past HTTP-date floors to 0
  - `test_invalid_header` - Returns None on invalid
  - `test_invalid_retry_after_values_log_debug_and_return_none` - Logs malformed headers
  **TestRetryAndCall**
  - `test_retry_after_honored` - Retry-After overrides backoff
  - `test_exponential_backoff` - Exponential backoff without jitter
  - `test_exponential_backoff_with_jitter` - Backoff with jitter
  - `test_gives_up_and_surfaces_last_error` - Propagates last error
  - `test_success_on_first_attempt` - Immediate success
  - `test_non_retryable_error_propagates` - Non-retryable error propagates
  - `test_retryable_then_non_retryable_error` - Stops after non-retryable error

### `tests/unit/utils/test_symbols.py`
- Purpose: SYMBOLS parsing/validation helpers
- Tests:
  **TestParseSymbols**
  - `test_basic_trim_uppercase_order_preserving_dedupe` - Trims/uppercases/dedupes
  - `test_filter_to_watchlist` - Filters to watchlist
  - `test_validation_toggle_true_skips_false_keeps` - Validation toggle behavior
  - `test_empty_input_returns_empty_list` - Empty input returns []
  - `test_mixed_valid_invalid_tokens_logs_when_validate_true` - Logs on invalid tokens
  - `test_share_class_and_suffix_symbols_allowed` - Accepts share-class suffixes and digits

### `tests/unit/workflows/test_poller.py`
- Purpose: DataPoller orchestration
- Tags: [async]
- Tests:
  **TestDataPoller**
  - `test_poll_once_stores_and_updates_watermark` - Stores and updates watermark
  - `test_poll_once_collects_errors` - Aggregates provider errors
  - `test_poll_once_no_data_no_watermark` - No data keeps watermark None
  - `test_poller_quick_shutdown` - Stops quickly on stop()
  - `test_poller_custom_poll_interval` - Accepts custom intervals
  - `test_macro_provider_min_id_passed_and_watermark_updated` - Macro provider uses min_id and updates watermark
  - `test_updates_news_since_iso_and_macro_min_id_independently` - Updates both watermarks
