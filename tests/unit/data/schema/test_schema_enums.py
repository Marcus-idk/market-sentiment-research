"""Tests enum value constraints and locks critical enum values against changes."""

import sqlite3

import pytest

from data.models import AnalysisType, NewsType, Session, Stance, Urgency
from data.storage.db_context import _cursor_context
from data.storage.state_enums import Provider, Scope, Stream


class TestEnumValueLocks:
    """Test that enum values never change (would break database)."""

    def test_session_enum_values_unchanged(self):
        """Lock Session enum values - these are stored in database."""
        assert Session.REG.value == "REG"
        assert Session.PRE.value == "PRE"
        assert Session.POST.value == "POST"
        assert Session.CLOSED.value == "CLOSED"

        assert len(Session) == 4
        assert set(s.value for s in Session) == {"REG", "PRE", "POST", "CLOSED"}

    def test_stance_enum_values_unchanged(self):
        """Lock Stance enum values - these are stored in database."""
        assert Stance.BULL.value == "BULL"
        assert Stance.BEAR.value == "BEAR"
        assert Stance.NEUTRAL.value == "NEUTRAL"

        assert len(Stance) == 3
        assert set(s.value for s in Stance) == {"BULL", "BEAR", "NEUTRAL"}

    def test_analysis_type_enum_values_unchanged(self):
        """Lock AnalysisType enum values - these are stored in database."""
        assert AnalysisType.NEWS_ANALYSIS.value == "news_analysis"
        assert AnalysisType.SENTIMENT_ANALYSIS.value == "sentiment_analysis"
        assert AnalysisType.SEC_FILINGS.value == "sec_filings"
        assert AnalysisType.HEAD_TRADER.value == "head_trader"

        assert len(AnalysisType) == 4
        assert set(a.value for a in AnalysisType) == {
            "news_analysis",
            "sentiment_analysis",
            "sec_filings",
            "head_trader",
        }

    def test_news_type_enum_values_unchanged(self):
        """Lock NewsType values - stored in database."""
        assert NewsType.MACRO.value == "macro"
        assert NewsType.COMPANY_SPECIFIC.value == "company_specific"
        assert len(NewsType) == 2
        assert set(news_type.value for news_type in NewsType) == {
            "macro",
            "company_specific",
        }

    def test_urgency_enum_values_unchanged(self):
        """Lock Urgency enum values - for future database storage."""
        assert Urgency.URGENT.value == "URGENT"
        assert Urgency.NOT_URGENT.value == "NOT_URGENT"

        assert len(Urgency) == 2
        assert set(u.value for u in Urgency) == {"URGENT", "NOT_URGENT"}

    def test_last_seen_state_enum_values_unchanged(self):
        """Lock Provider/Stream/Scope enum values used in last_seen_state."""
        assert Provider.FINNHUB.value == "FINNHUB"
        assert Provider.POLYGON.value == "POLYGON"
        assert Provider.REDDIT.value == "REDDIT"
        assert set(p.value for p in Provider) == {"FINNHUB", "POLYGON", "REDDIT"}

        assert Stream.COMPANY.value == "COMPANY"
        assert Stream.MACRO.value == "MACRO"
        assert Stream.SOCIAL.value == "SOCIAL"
        assert set(s.value for s in Stream) == {"COMPANY", "MACRO", "SOCIAL"}

        assert Scope.GLOBAL.value == "GLOBAL"
        assert Scope.SYMBOL.value == "SYMBOL"
        assert set(sc.value for sc in Scope) == {"GLOBAL", "SYMBOL"}


class TestEnumConstraints:
    """Test enum value constraints."""

    def test_session_enum_values(self, temp_db):
        """Test session IN ('REG', 'PRE', 'POST', 'CLOSED') constraint."""
        with _cursor_context(temp_db) as cursor:
            # Valid enum values - test data with different hours for each session type
            session_hours = {"REG": "14", "PRE": "09", "POST": "21", "CLOSED": "02"}
            for session in ["REG", "PRE", "POST", "CLOSED"]:
                cursor.execute(
                    """
                    INSERT INTO price_data (symbol, timestamp_iso, price, session)
                    VALUES (?, ?, '150.00', ?)
                """,
                    (f"TEST_{session}", f"2024-01-01T{session_hours[session]}:00:00Z", session),
                )

            # Invalid: wrong case
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price, session)
                    VALUES ('TEST', '2024-01-01T14:00:00Z', '150.00', 'reg')
                """)

            # Invalid: not in enum
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute("""
                    INSERT INTO price_data (symbol, timestamp_iso, price, session)
                    VALUES ('TEST', '2024-01-01T15:00:00Z', '150.00', 'EXTENDED')
                """)

    def test_stance_enum_values(self, temp_db):
        """Test stance IN ('BULL', 'BEAR', 'NEUTRAL') constraint."""
        with _cursor_context(temp_db) as cursor:
            # Valid values
            for stance in ["BULL", "BEAR", "NEUTRAL"]:
                cursor.execute(
                    """
                    INSERT INTO analysis_results 
                    (
                        symbol,
                        analysis_type,
                        model_name,
                        stance,
                        confidence_score,
                        last_updated_iso,
                        result_json
                    )
                    VALUES (
                        ?, 'news_analysis', 'gpt-4', ?, 0.75,
                        '2024-01-01T10:00:00Z', '{}'
                    )
                """,
                    (f"TEST_{stance}", stance),
                )

            # Invalid: lowercase
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO analysis_results 
                    (
                        symbol,
                        analysis_type,
                        model_name,
                        stance,
                        confidence_score,
                        last_updated_iso,
                        result_json
                    )
                    VALUES (
                        'TEST', 'sentiment_analysis', 'gpt-4', 'bull', 0.75,
                        '2024-01-01T10:00:00Z', '{}'
                    )
                """
                )

    def test_analysis_type_enum_values(self, temp_db):
        """Test analysis_type enum constraint."""
        with _cursor_context(temp_db) as cursor:
            # Valid values
            valid_types = ["news_analysis", "sentiment_analysis", "sec_filings", "head_trader"]
            for i, atype in enumerate(valid_types):
                cursor.execute(
                    """
                    INSERT INTO analysis_results 
                    (
                        symbol,
                        analysis_type,
                        model_name,
                        stance,
                        confidence_score,
                        last_updated_iso,
                        result_json
                    )
                    VALUES (
                        ?, ?, 'gpt-4', 'BULL', 0.75,
                        '2024-01-01T10:00:00Z', '{}'
                    )
                """,
                    (f"TEST{i}", atype),
                )

            # Invalid: uppercase
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO analysis_results 
                    (
                        symbol,
                        analysis_type,
                        model_name,
                        stance,
                        confidence_score,
                        last_updated_iso,
                        result_json
                    )
                    VALUES (
                        'INVALID', 'NEWS_ANALYSIS', 'gpt-4', 'BULL', 0.75,
                        '2024-01-01T10:00:00Z', '{}'
                    )
                """
                )

    def test_news_type_enum_values(self, temp_db):
        """Test news_items.news_type constraint values."""
        with _cursor_context(temp_db) as cursor:
            for suffix, news_type in enumerate(["macro", "company_specific"]):
                cursor.execute(
                    """
                    INSERT INTO news_items (
                        url,
                        headline,
                        content,
                        published_iso,
                        source,
                        news_type
                    )
                    VALUES (
                        'http://example.com/enum-' || ?,
                        'Enum Value',
                        NULL,
                        '2024-01-01T10:00:00Z',
                        'test',
                        ?
                    )
                """,
                    (suffix, news_type),
                )

            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO news_items (
                        url,
                        headline,
                        content,
                        published_iso,
                        source,
                        news_type
                    )
                    VALUES (
                        'http://example.com/enum-invalid',
                        'Invalid Enum',
                        NULL,
                        '2024-01-01T10:00:00Z',
                        'test',
                        'invalid'
                    )
                """
                )

            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO news_items (
                        url,
                        headline,
                        content,
                        published_iso,
                        source,
                        news_type
                    )
                    VALUES (
                        'http://example.com/enum-invalid-case',
                        'Invalid Enum Case',
                        NULL,
                        '2024-01-01T10:00:00Z',
                        'test',
                        'MACRO'
                    )
                """
                )

    def test_news_symbols_is_important_constraint(self, temp_db):
        """Test news_symbols.is_important constraint allows NULL/0/1 only."""
        with _cursor_context(temp_db) as cursor:
            cursor.execute(
                """
                INSERT INTO news_items (
                    url,
                    headline,
                    content,
                    published_iso,
                    source,
                    news_type
                )
                VALUES (
                    'http://example.com/symbol',
                    'Symbol Test',
                    NULL,
                    '2024-01-01T10:00:00Z',
                    'test',
                    'macro'
                )
            """
            )

            # NULL is allowed
            cursor.execute(
                """
                INSERT INTO news_symbols (url, symbol, is_important)
                VALUES ('http://example.com/symbol', 'AAPL', NULL)
            """
            )

            # 0 and 1 are allowed
            cursor.execute(
                """
                INSERT INTO news_symbols (url, symbol, is_important)
                VALUES ('http://example.com/symbol', 'TSLA', 0)
            """
            )
            cursor.execute(
                """
                INSERT INTO news_symbols (url, symbol, is_important)
                VALUES ('http://example.com/symbol', 'MSFT', 1)
            """
            )

            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                INSERT INTO news_symbols (url, symbol, is_important)
                VALUES ('http://example.com/symbol', 'NVDA', 5)
            """
                )

    def test_last_seen_state_constraints(self, temp_db):
        """Test last_seen_state provider/stream/scope CHECK constraints."""
        with _cursor_context(temp_db) as cursor:
            # Valid values - timestamp only
            cursor.execute(
                """
                INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
                VALUES ('FINNHUB', 'COMPANY', 'GLOBAL', '__GLOBAL__', '2024-01-01T00:00:00Z', NULL)
            """
            )

            # Valid values - id only
            cursor.execute(
                """
                INSERT INTO last_seen_state (provider, stream, scope, symbol, timestamp, id)
                VALUES ('POLYGON', 'MACRO', 'SYMBOL', 'AAPL', NULL, 5)
            """
            )

            # Invalid provider
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO last_seen_state (provider, stream, scope, symbol)
                    VALUES ('FOO', 'COMPANY', 'GLOBAL', '__GLOBAL__')
                """
                )

            # Invalid stream
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO last_seen_state (provider, stream, scope, symbol)
                    VALUES ('FINNHUB', 'PRICE', 'GLOBAL', '__GLOBAL__')
                """
                )

            # Invalid scope
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                cursor.execute(
                    """
                    INSERT INTO last_seen_state (provider, stream, scope, symbol)
                    VALUES ('FINNHUB', 'COMPANY', 'LOCAL', '__GLOBAL__')
                """
                )
