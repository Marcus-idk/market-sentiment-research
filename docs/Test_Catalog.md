# Test Catalog — Complete Test Inventory

This document enumerates all Python files under `tests/` and what they cover (test modules, fixtures, factories, shared stubs).
Keep it human-scannable and low-churn; do not duplicate this inventory in other docs.

## Rules to Follow When Updating This
- Keep this as the single source for the test inventory.
- Update when a test file is added/removed, or when tests are added/removed/renamed.
- For each file in `tests/`, include: Purpose, Tags (optional), key Fixtures/factories (optional), Tests (if any), Notes (optional).
- List ALL test functions with one-line descriptions of what they validate; for helper-only files (e.g., factories, shared stubs), list the key helpers instead.
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

### `tests/__init__.py`
- Purpose: Package marker for test suite
- Tests: (none)

### `tests/conftest.py`
- Purpose: Project-wide fixtures and SQLite cleanup helpers
- Fixtures: `temp_db_path`, `temp_db`, `mock_http_client`
- Helpers: `cleanup_sqlite_artifacts` - checkpoints and removes WAL/journal files
- Tests: (none)

### `tests/factories/__init__.py`
- Purpose: Export shared factory helpers for tests
- Helpers: `make_news_item`, `make_news_entry`, `make_price_data`, `make_analysis_result`, `make_holdings`, `make_social_discussion`
- Tests: (none)

### `tests/factories/models.py`
- Purpose: Factory implementations for data model instances with sane defaults
- Helpers: `make_news_item`, `make_news_entry`, `make_price_data`, `make_analysis_result`, `make_holdings`, `make_social_discussion`
- Tests: (none)

### `tests/integration/conftest.py`
- Purpose: Marks integration suite and provides provider settings
- Tags: [integration]
- Fixtures: `finnhub_settings`, `polygon_settings`, `reddit_settings` (skip when env vars missing)
- Tests: (none)

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

### `tests/integration/data/providers/test_reddit_live.py`
- Purpose: Live validation for Reddit social provider
- Tags: [network] [async]
- Tests:
  - `test_live_validate_connection` - Reddit credentials validate against API
  - `test_live_discussions_fetch` - Fetches recent AAPL discussions with valid fields
- Notes: Requires REDDIT_CLIENT_ID/SECRET/USER_AGENT; network access

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

### `tests/integration/llm/conftest.py`
- Purpose: ProviderSpec fixture for LLM integration contracts
- Tags: [integration]
- Fixtures: `provider_spec` parametrized over OpenAI and Gemini
- Helpers: `ProviderSpec` helper with factory methods for code/search tool configs
- Tests: (none)

### `tests/integration/llm/helpers.py`
- Purpose: Shared helpers for LLM integration tests
- Tags: [async]
- Helpers: `make_base64_blob`, `extract_hex64`, `fetch_featured_wiki`, `normalize_title`
- Tests: (none)

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

### `tests/unit/config/providers/test_reddit_settings.py`
- Purpose: Reddit-specific env loading and defaults
- Tests:
  **TestRedditSettings**
  - `test_from_env_success` - Loads all env vars and keeps default retry config
  - `test_from_env_missing_client_id` - Missing client id raises ValueError
  - `test_from_env_missing_client_secret` - Missing client secret raises ValueError
  - `test_from_env_missing_user_agent` - Missing user agent raises ValueError
  - `test_from_env_strips_whitespace` - Strips surrounding whitespace

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

### `tests/unit/data/providers/conftest.py`
- Purpose: Shared provider specs and client configs for provider contract tests
- Fixtures: `provider_spec_company`, `provider_spec_macro`, `provider_spec_prices`, `client_spec`
- Helpers: `CompanyProviderSpec`, `MacroProviderSpec`, `PriceProviderSpec`, `ClientSpec` factories
- Tests: (none)

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
  - `test_filters_articles_with_buffer` - Applies configured overlap buffer window
  - `test_date_window_params_with_since` - Adds correct date/ISO params with since
  - `test_date_window_params_without_since` - Adds correct date/ISO params without since
  - `test_symbol_normalization_uppercases` - Uppercases symbol list
  - `test_summary_copied_to_content` - Copies summary to content
  - `test_per_symbol_error_isolation` - Isolates errors per symbol
  - `test_structural_error_raises` - Malformed response raises DataSourceError
  - `test_empty_response_returns_empty_list` - Empty response returns []
  - `test_symbol_since_map_takes_precedence` - Per-symbol cursor overrides global since when present
  - `test_symbol_cursor_falls_back_to_global_or_none` - Falls back to global cursor or None when no per-symbol entry

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
  - `test_structural_error_non_dict_response` - Non-dict API response raises DataSourceError
  - `test_parse_exception_skips_article_and_continues` - Skips malformed article; processes remaining
  - `test_invalid_timestamp_skips_article` - Invalid timestamp causes skip
  - `test_newsitem_validation_failure_skips_article` - Invalid article URL rejected
  - `test_newsentry_validation_failure_skips_symbol` - Drops invalid symbol; keeps valid

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
  - `test_fetch_incremental_paginates_with_min_id` - Paginates using minId and tracks last_fetched_max_id
  - `test_fetch_incremental_stops_at_bootstrap_cutoff` - Stops at bootstrap cutoff based on macro lookback window

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
  - `test_fetch_symbol_news_applies_buffer_filter` - Applies buffer filter and logs when API returns too-old articles

### `tests/unit/data/providers/test_polygon_macro_news.py`
- Purpose: Polygon macro news specifics (beyond shared tests)
- Tags: [async]
- Tests:
  **TestPolygonMacroNewsProvider**
  - `test_fetch_incremental_handles_pagination` - Handles next_url pagination
  - `test_since_buffer_applied` - Applies 2‑minute since buffer
  - `test_empty_results_stops_pagination` - Stops on empty results
  - `test_next_url_without_cursor_stops_pagination` - Halts when next_url lacks cursor
  - `test_extract_cursor_from_next_url` - Extracts cursor value
  - `test_extract_cursor_exception_returns_none` - Returns None on invalid next_url
  - `test_non_dict_publisher_defaults_to_polygon` - Defaults publisher to "Polygon"

### `tests/unit/data/providers/test_reddit_client.py`
- Purpose: RedditClient initialization and validation
- Tests:
  **TestRedditClient**
  - `test_init_sets_read_only_and_creds` - Passes creds to praw.Reddit and sets read_only
  - `test_validate_connection_success` - Returns True when /me is truthy
  - `test_validate_connection_praw_error_logs_and_returns_false` - Prawcore errors warn and return False
  - `test_validate_connection_generic_error_returns_false` - Generic errors warn and return False

### `tests/unit/data/providers/test_reddit_social.py`
- Purpose: RedditSocialProvider cursor planning, parsing, and content building
- Tags: [async]
- Tests:
  **TestRedditSocialProviderBasics**
  - `test_symbol_normalization_uppercases_and_filters` - Normalizes and filters symbol list in __init__
  - `test_validate_connection_delegates_to_client` - validate_connection delegates to the underlying client
  **TestFetchIncremental**
  - `test_fetch_incremental_empty_symbols_returns_empty` - No symbols → empty list
  - `test_fetch_incremental_bootstrap_uses_week_filter` - Bootstrap uses week time_filter and first-run window
  - `test_fetch_incremental_cursor_uses_hour_with_overlap` - Cursor path uses overlap buffer and hour filter
  - `test_resolve_symbol_cursor_prefers_symbol_map_over_global` - Per-symbol cursor overrides global
  - `test_fetch_incremental_praw_error_skips_symbol_not_all` - Praw errors skip only failing symbol
  **TestParseSubmission**
  - `test_parse_submission_valid_returns_discussion` - Parses valid submission into SocialDiscussion
  - `test_parse_submission_invalid_returns_none` - Missing fields/invalid URLs return None
  - `test_parse_submission_returns_none_when_before_start` - Drops submissions at/before start_time
  **TestBuildContent**
  - `test_build_content_combines_selftext_and_comments` - Selftext plus comments combined with separators
  - `test_build_content_empty_returns_none` - No content/comments returns None

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
  - `test_last_seen_state_enum_values_unchanged` - Locks Provider/Stream/Scope enum values used in `last_seen_state`
  **TestEnumConstraints**
  - `test_session_enum_values` - Enforces session constraint
  - `test_stance_enum_values` - Enforces stance constraint
  - `test_analysis_type_enum_values` - Enforces analysis_type constraint
  - `test_news_type_enum_values` - Enforces news_type constraint
  - `test_news_symbols_is_important_constraint` - `news_symbols.is_important` allows NULL/0/1 only
  - `test_last_seen_state_constraints` - Enforces `last_seen_state` provider/stream/scope CHECK constraints

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

### `tests/unit/data/schema/test_schema_last_seen_state.py`
- Purpose: Watermark table schema and constraints for `last_seen_state`
- Tests:
  **TestLastSeenStateSchema**
  - `test_table_has_expected_columns` - Validates last_seen_state column layout via PRAGMA table_info
  - `test_primary_key_enforces_uniqueness` - Primary key prevents duplicate provider/stream/scope/symbol rows
  - `test_scope_check_constraint` - Scope CHECK constraint rejects invalid values

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

### `tests/unit/data/storage/test_storage_core.py`
- Purpose: Edge-case coverage for SQLite lifecycle helpers and JSON1 checks
- Tests:
  - `test_connect_logs_when_foreign_keys_pragma_fails` - Logs when foreign_keys pragma fails
  - `test_connect_logs_when_busy_timeout_pragma_fails` - Logs when busy_timeout pragma fails
  - `test_connect_logs_when_wal_pragma_fails` - Logs when journal_mode WAL pragma fails
  - `test_connect_logs_when_sync_pragma_fails` - Logs when synchronous pragma fails
  - `test_connect_sets_wal_and_synchronous` - Enforces WAL + synchronous=NORMAL on connect
  - `test_check_json1_support_returns_false_when_extension_missing` - Returns False and logs when JSON1 missing
  - `test_init_database_raises_when_json1_missing` - Raises when JSON1 support is unavailable
  - `test_finalize_database_raises_when_path_missing` - Raises FileNotFoundError for missing DB path
  - `test_finalize_database_switches_to_delete_mode` - Journal mode switches to DELETE after finalize
  - `test_finalize_database_runs_checkpoint` - finalize_database sets synchronous=FULL, checkpoints, and commits

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

### `tests/unit/data/storage/test_storage_watermark.py`
- Purpose: Typed watermark helpers for `last_seen_state`
- Tests:
  **TestTimestampCursors**
  - `test_global_timestamp_roundtrip` - Global timestamp stored with __GLOBAL__ symbol and round-trips as UTC
  - `test_symbol_timestamp_roundtrip` - Per-symbol timestamps stored and round-trip correctly
  - `test_timestamp_upsert_is_monotonic` - Newer timestamps stick; older writes ignored
  **TestSymbolNormalization**
  - `test_symbol_scope_requires_non_empty_value` - Symbol scope rejects None, empty, and reserved __GLOBAL__ sentinel
  - `test_global_scope_rejects_symbols` - Global scope requires None and normalizes to __GLOBAL__; rejects non-None symbols
  **TestIdCursors**
  - `test_global_id_roundtrip` - Global ID watermark stored and retrieved as integer
  - `test_corrupted_id_row_returns_none` - Corrupted/non-integer ID rows are logged and return None
  - `test_id_upsert_is_monotonic` - Newer IDs replace older values
  **TestEnumLocks**
  - `test_provider_enum_reddit_value` - Locks Provider.REDDIT value
  - `test_stream_enum_social_value` - Locks Stream.SOCIAL value
  **TestSchemaConstraints**
  - `test_xor_constraint_blocks_timestamp_and_id` - XOR constraint blocks rows with both timestamp and id
  - `test_global_scope_defaults_symbol_to_global` - Global scope writes store __GLOBAL__ sentinel

### `tests/unit/data/storage/test_storage_llm_batch.py`
- Purpose: LLM batch commit flow
- Tests:
  **TestBatchOperations**
  - `test_commit_llm_batch_atomic_transaction` - Atomically deletes rows with created_at_iso ≤ cutoff and returns deletion counts
  - `test_commit_llm_batch_empty_database` - Empty database yields zero deletion counts
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

### `tests/unit/data/storage/test_storage_social.py`
- Purpose: Social discussion storage CRUD
- Tests:
  **TestStoreSocialDiscussions**
  - `test_store_social_discussions_inserts` - Inserts unique rows with normalized fields
  - `test_store_social_discussions_upserts_on_source_id` - Upserts on (source, source_id) conflicts
  - `test_store_social_discussions_empty_list_noop` - Empty list no-op
  **TestGetSocialDiscussions**
  - `test_get_social_discussions_since_filters_by_timestamp` - Filters by published cutoff
  - `test_get_social_discussions_since_filters_by_symbol_case_insensitive` - Symbol filter uppercases input
  - `test_get_social_discussions_since_sorted_ascending` - Results ordered ascending by published
  - `test_store_and_get_preserves_content_and_url_normalization` - Content round-trips; URLs normalized

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
  **TestSocialDataSourceContract**
  - `test_requires_fetch_incremental` - Enforces social fetch_incremental implementation
  - `test_concrete_implementation_satisfies_contract` - Concrete subclass handles cursors
  **TestDataSourceErrorContract**
  - `test_exception_inheritance` - DataSourceError hierarchy

### `tests/unit/data/test_models.py`
- Purpose: Dataclasses and enums validation
- Tests:
  **TestNewsItem**
  - `test_newsitem_valid_creation` - Valid NewsItem requires core fields and normalizes to UTC
  - `test_newsitem_url_validation_accepts_http` - Accepts http/https URLs with valid hosts
  - `test_newsitem_url_validation_rejects_non_http` - Rejects non-http(s) or malformed URLs
  - `test_newsitem_empty_field_validation` - Rejects empty headline/source after stripping
  - `test_newsitem_news_type_variants` - Accepts enum instances or exact NewsType strings
  - `test_newsitem_timezone_normalization` - Normalizes naive published datetimes to UTC
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

### `tests/unit/data/test_models_social.py`
- Purpose: SocialDiscussion validation and normalization
- Tests:
  **TestSocialDiscussionValidation**
  - `test_required_fields_raise_value_error` - Empty/invalid fields raise ValueError
  - `test_non_datetime_published_raises` - Non-datetime published raises ValueError
  **TestSocialDiscussionNormalization**
  - `test_normalization_strips_and_uppercases` - Trims fields, uppercases symbol, normalizes published to UTC

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
- Fixtures: `monkeypatch`, `caplog`
- Tests:
  **TestOpenAIProvider**
  - `test_generate_passes_expected_args` - Forwards args (model, input, temp, reasoning, tools, tool_choice)
  - `test_generate_respects_custom_reasoning` - Uses custom reasoning; omits temperature when None
  - `test_generate_coerces_gpt5_tool_choice_to_auto` - Coerces non-`auto` tool_choice to `auto` for GPT-5 and logs warning
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
  - `test_generate_rejects_tool_choice_without_function_declarations` - Raises ValueError when tool_choice is set without function_declarations (built-ins only)
  - `test_generate_uses_default_thinking` - Applies default thinking budget
  - `test_generate_uses_custom_thinking` - Applies custom thinking config
  - `test_generate_clamps_small_thinking_budget` - Clamps small thinking budgets up to minimum
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
  - `test_408_request_timeout_is_retryable` - 408 treated as retryable and honors Retry-After
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
  - `test_numeric_zero_values` - Honors zero Retry-After inputs
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

### `tests/unit/run_poller/test_build_config_reddit.py`
- Purpose: build_config Reddit credential enforcement
- Tests:
  **TestBuildConfigReddit**
  - `test_build_config_requires_reddit_creds` - Missing Reddit env vars raise ValueError
  - `test_build_config_succeeds_with_reddit_creds` - Loads reddit_settings when all env vars set

### `tests/unit/workflows/test_poller.py`
- Purpose: DataPoller orchestration
- Tags: [async]
- Tests:
  **TestDataPoller**
  - `test_poll_once_collects_errors` - Aggregates provider errors without aborting price processing
  - `test_poller_quick_shutdown` - Stops quickly on stop()
  - `test_poller_custom_poll_interval` - Accepts custom intervals
  - `test_poll_once_collects_price_provider_errors` - Reports price provider failures without aborting
  - `test_fetch_all_data_forwards_cursor_kwargs` - Forwards since/min_id/symbol_since_map into provider fetch calls
  - `test_fetch_all_data_routes_company_and_macro_news` - Routes entries into company vs macro collections based on stream type
  - `test_fetch_all_data_handles_social_providers` - Passes cursors into social providers and captures errors
  - `test_poll_once_logs_no_price_data` - Logs when no price data is fetched
  - `test_poll_once_includes_social_stats` - Social counts surfaced in poll stats with errors merged
  - `test_poll_once_catches_cycle_error_and_appends` - Catches cycle error and appends to stats

  **TestDataPollerProcessPrices**
  - `test_process_prices_returns_zero_on_empty_input` - Returns 0 and stores nothing on empty input
  - `test_process_prices_primary_missing_symbol_warns_and_skips` - Warns and skips when primary lacks symbol
  - `test_process_prices_missing_secondary_provider_is_ignored` - Stores primary; missing secondary ignored
  - `test_process_prices_secondary_missing_symbol_warns` - Warns when secondary lacks symbol; primary stored
  - `test_process_prices_mismatch_logs_error_and_keeps_primary` - Logs mismatch (≥ $0.01); stores primary only
  - `test_process_prices_handles_duplicate_class_instances` - Handles duplicate class instances; primary stored; mismatch logged

  **TestDataPollerSocialProcessing**
  - `test_process_social_stores_and_commits` - Stores social discussions and commits per-provider watermarks
  - `test_process_social_logs_when_empty` - Logs notice and returns zero when no social items

  **TestDataPollerNewsProcessing**
  - `test_process_news_commits_each_provider` - Commits watermark updates once per provider with that provider's entries
  - `test_process_news_logs_urgency_detection_failures` - Logs urgency detection failures but still returns correct count
  - `test_process_news_logs_when_empty` - Logs when there are no news items to process
  - `test_log_urgent_items_logs_summary` - Logs bounded urgent-items summary with ellipsis

  **TestDataPollerRunLoop**
  - `test_run_logs_completed_with_errors` - Logs "completed with errors" when errors present
  - `test_run_skips_wait_when_sleep_time_zero` - Skips wait when interval yields zero sleep
  - `test_run_handles_wait_timeout` - Handles wait timeout and continues
  - `test_run_handles_wait_cancelled` - Handles cancelled wait and exits

### `tests/unit/workflows/test_watermark_engine.py`
- Purpose: WatermarkEngine planning and commit logic
- Tests:
  **TestBuildPlan**
  - `test_finnhub_macro_plan_uses_id_cursor` - Uses stored ID watermark for Finnhub macro streams
  - `test_finnhub_company_plan_maps_each_symbol` - Builds per-symbol timestamp cursors with bootstrap for new symbols
  - `test_polygon_company_plan_bootstraps_symbols` - Uses global timestamp watermark and per-symbol bootstrap overrides
  - `test_reddit_social_plan_uses_per_symbol_map` - Per-symbol social cursors use first-run window or stored cursor
  **TestCommitUpdates**
  - `test_symbol_scope_clamps_future` - Clamps per-symbol timestamps slightly in the future
  - `test_global_scope_bootstrap_updates` - Updates global and per-symbol timestamps with clamping and max-of-existing behavior
  - `test_id_scope_writes_last_fetched_max` - Writes last_fetched_max_id for ID-based macro streams
  - `test_id_scope_noop_without_last_fetched` - No-op when last_fetched_max_id is None
  - `test_social_scope_commits_per_symbol_and_clamps_future` - Social watermarks clamped and monotonic per symbol
  **TestHelpers**
  - `test_get_settings_missing_attribute_raises` - _get_settings raises when provider lacks settings attribute
  - `test_is_macro_stream_matches_rule` - is_macro_stream returns True only for macro providers (False for Reddit)
