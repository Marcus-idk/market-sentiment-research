"""Symbols parsing and filtering via parse_symbols()."""

import logging

from utils.symbols import parse_symbols


class TestParseSymbols:
    """Test parse_symbols function"""

    def test_basic_trim_uppercase_order_preserving_dedupe(self):
        """Test core parsing: trim, uppercase, dedupe while preserving order"""
        result = parse_symbols(" aapl , MSFT, aapl, tsla ")

        assert result == ["AAPL", "MSFT", "TSLA"]
        # Verify order preserved (AAPL before TSLA)
        assert result.index("AAPL") < result.index("TSLA")
        # Verify second 'aapl' was deduped
        assert result.count("AAPL") == 1

    def test_filter_to_watchlist(self):
        """Test watchlist filtering keeps only allowed symbols"""
        result = parse_symbols("AAPL,MSFT,GOOG", filter_to=["AAPL", "MSFT"])

        assert result == ["AAPL", "MSFT"]
        assert "GOOG" not in result

    def test_validation_toggle_true_skips_false_keeps(self):
        """Test validation on/off behavior"""
        # With validation (default): invalid symbols filtered out
        result_strict = parse_symbols("AAPL,TOOLONG,123", validate=True)
        assert result_strict == ["AAPL"]

        # Without validation: invalid symbols kept
        result_lenient = parse_symbols("AAPL,TOOLONG,123", validate=False)
        assert result_lenient == ["AAPL", "TOOLONG", "123"]

    def test_fail_on_invalid_true_returns_empty_list(self):
        """When fail_on_invalid=True, any invalid token invalidates the whole list."""
        result = parse_symbols("AAPL,123,MSFT", validate=True, fail_on_invalid=True)
        assert result == []

    def test_empty_input_returns_empty_list(self):
        """Test graceful handling of empty/null inputs"""
        # Empty string
        assert parse_symbols("") == []

        # None
        assert parse_symbols(None) == []

        # Whitespace only
        assert parse_symbols("   ") == []

        # Only commas and whitespace
        assert parse_symbols("  ,  , ") == []

    def test_mixed_valid_invalid_tokens_logs_when_validate_true(self, caplog):
        """Test logging behavior for invalid symbols during validation"""
        with caplog.at_level(logging.DEBUG):
            result = parse_symbols("AAPL,123,MSFT", validate=True)

        # Returns only valid symbols
        assert result == ["AAPL", "MSFT"]

        # Logged the invalid symbol with a generic label
        assert any(
            "Unexpected symbol entry format: 123" in record.message for record in caplog.records
        )

    def test_share_class_and_suffix_symbols_allowed(self):
        """Share-class suffixes (dot/dash) and digits after first char should be accepted."""
        result = parse_symbols("BRK.B,BF-B,PSA.P,GOOG1")

        assert result == ["BRK.B", "BF-B", "PSA.P", "GOOG1"]
