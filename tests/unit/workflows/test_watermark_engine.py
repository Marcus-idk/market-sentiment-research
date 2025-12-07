"""WatermarkEngine planning and commit logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from config.providers.finnhub import FinnhubSettings
from config.providers.polygon import PolygonSettings
from config.providers.reddit import RedditSettings
from data.base import NewsDataSource
from data.providers.finnhub import FinnhubMacroNewsProvider, FinnhubNewsProvider
from data.providers.polygon import PolygonMacroNewsProvider, PolygonNewsProvider
from data.providers.reddit import RedditSocialProvider
from data.storage import (
    get_last_seen_id,
    get_last_seen_timestamp,
    set_last_seen_id,
    set_last_seen_timestamp,
)
from data.storage.state_enums import Provider, Scope, Stream
from tests.factories import make_news_entry, make_social_discussion
from workflows import watermarks as watermarks_module
from workflows.watermarks import WatermarkEngine, is_macro_stream


def _make_engine(temp_db: str) -> WatermarkEngine:
    return WatermarkEngine(temp_db)


class TestBuildPlan:
    """Covers cursor planning for different providers."""

    def test_finnhub_macro_plan_uses_id_cursor(self, temp_db):
        """Test finnhub macro plan uses id cursor."""
        provider = FinnhubMacroNewsProvider(FinnhubSettings(api_key="test"), ["AAPL"])
        set_last_seen_id(temp_db, Provider.FINNHUB, Stream.MACRO, Scope.GLOBAL, 200)

        plan = _make_engine(temp_db).build_plan(provider)

        assert plan.min_id == 200
        assert plan.since is None
        assert plan.symbol_since_map is None

    def test_finnhub_company_plan_maps_each_symbol(self, temp_db, monkeypatch):
        """Test finnhub company plan maps each symbol."""
        provider = FinnhubNewsProvider(FinnhubSettings(api_key="test"), ["AAPL", "TSLA"])
        fixed_now = datetime(2024, 1, 20, 12, 0, tzinfo=UTC)
        monkeypatch.setattr(watermarks_module, "_utc_now", lambda: fixed_now)

        existing = datetime(2024, 1, 18, 9, 30, tzinfo=UTC)
        set_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.COMPANY,
            Scope.SYMBOL,
            existing,
            symbol="AAPL",
        )

        plan = _make_engine(temp_db).build_plan(provider)

        assert plan.since is None
        assert plan.min_id is None
        expected_tsla = fixed_now - timedelta(days=provider.settings.company_news_first_run_days)
        assert plan.symbol_since_map == {
            "AAPL": existing,
            "TSLA": expected_tsla,
        }

    def test_polygon_company_plan_bootstraps_symbols(self, temp_db, monkeypatch):
        """Test polygon company plan bootstraps symbols."""
        provider = PolygonNewsProvider(PolygonSettings(api_key="test"), ["AAPL", "MSFT"])
        fixed_now = datetime(2024, 1, 25, 15, 0, tzinfo=UTC)
        monkeypatch.setattr(watermarks_module, "_utc_now", lambda: fixed_now)

        base_since = datetime(2024, 1, 20, 12, 0, tzinfo=UTC)
        stale_symbol = base_since - timedelta(days=1)

        set_last_seen_timestamp(
            temp_db,
            Provider.POLYGON,
            Stream.COMPANY,
            Scope.GLOBAL,
            base_since,
        )
        set_last_seen_timestamp(
            temp_db,
            Provider.POLYGON,
            Stream.COMPANY,
            Scope.SYMBOL,
            stale_symbol,
            symbol="AAPL",
        )

        plan = _make_engine(temp_db).build_plan(provider)

        assert plan.since == base_since
        override = fixed_now - timedelta(days=provider.settings.company_news_first_run_days)
        assert plan.symbol_since_map == {"AAPL": override, "MSFT": override}

    def test_reddit_social_plan_uses_per_symbol_map(self, temp_db, monkeypatch):
        """Reddit plan returns per-symbol cursors with first-run window."""
        settings = RedditSettings(client_id="id", client_secret="secret", user_agent="agent")
        provider = RedditSocialProvider(settings, ["AAPL", "TSLA"])
        fixed_now = datetime(2024, 4, 1, 12, 0, tzinfo=UTC)
        monkeypatch.setattr(watermarks_module, "_utc_now", lambda: fixed_now)

        existing = datetime(2024, 3, 31, 10, 0, tzinfo=UTC)
        set_last_seen_timestamp(
            temp_db,
            Provider.REDDIT,
            Stream.SOCIAL,
            Scope.SYMBOL,
            existing,
            symbol="AAPL",
        )

        plan = _make_engine(temp_db).build_plan(provider)

        baseline = fixed_now - timedelta(days=settings.social_news_first_run_days)
        assert plan.since is None
        assert plan.min_id is None
        assert plan.symbol_since_map == {
            "AAPL": existing,
            "TSLA": baseline,
        }


class TestCommitUpdates:
    """Watermark persistence per provider rule."""

    def test_symbol_scope_clamps_future(self, temp_db, monkeypatch):
        """Test symbol scope clamps future."""
        provider = FinnhubNewsProvider(FinnhubSettings(api_key="test"), ["AAPL", "TSLA"])
        fixed_now = datetime(2024, 2, 1, 12, 0, tzinfo=UTC)
        monkeypatch.setattr(watermarks_module, "_utc_now", lambda: fixed_now)

        entries = [
            make_news_entry(
                symbol="AAPL",
                published=fixed_now + timedelta(minutes=5),
            ),
            make_news_entry(
                symbol="TSLA",
                published=fixed_now - timedelta(minutes=10),
            ),
        ]

        _make_engine(temp_db).commit_updates(provider, entries)

        aapl_ts = get_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.COMPANY,
            Scope.SYMBOL,
            symbol="AAPL",
        )
        tsla_ts = get_last_seen_timestamp(
            temp_db,
            Provider.FINNHUB,
            Stream.COMPANY,
            Scope.SYMBOL,
            symbol="TSLA",
        )

        assert aapl_ts == fixed_now + timedelta(seconds=60)
        assert tsla_ts == fixed_now - timedelta(minutes=10)

    def test_global_scope_bootstrap_updates(self, temp_db, monkeypatch):
        """Test global scope bootstrap updates."""
        provider = PolygonNewsProvider(PolygonSettings(api_key="test"), ["AAPL", "MSFT"])
        fixed_now = datetime(2024, 3, 5, 18, 0, tzinfo=UTC)
        monkeypatch.setattr(watermarks_module, "_utc_now", lambda: fixed_now)

        existing = datetime(2024, 3, 5, 10, 0, tzinfo=UTC)
        set_last_seen_timestamp(
            temp_db,
            Provider.POLYGON,
            Stream.COMPANY,
            Scope.GLOBAL,
            existing,
        )

        future_entry = make_news_entry(
            symbol="AAPL",
            published=fixed_now + timedelta(minutes=5),
        )
        past_entry = make_news_entry(
            symbol="MSFT",
            published=fixed_now - timedelta(minutes=30),
        )

        _make_engine(temp_db).commit_updates(provider, [future_entry, past_entry])

        global_ts = get_last_seen_timestamp(
            temp_db,
            Provider.POLYGON,
            Stream.COMPANY,
            Scope.GLOBAL,
        )
        aapl_ts = get_last_seen_timestamp(
            temp_db,
            Provider.POLYGON,
            Stream.COMPANY,
            Scope.SYMBOL,
            symbol="AAPL",
        )
        msft_ts = get_last_seen_timestamp(
            temp_db,
            Provider.POLYGON,
            Stream.COMPANY,
            Scope.SYMBOL,
            symbol="MSFT",
        )

        clamped_future = fixed_now + timedelta(seconds=60)
        assert global_ts == clamped_future
        assert aapl_ts == clamped_future
        assert msft_ts == fixed_now - timedelta(minutes=30)

    def test_id_scope_writes_last_fetched_max(self, temp_db):
        """Test id scope writes last fetched max."""
        provider = FinnhubMacroNewsProvider(FinnhubSettings(api_key="test"), ["AAPL"])
        provider.last_fetched_max_id = 250

        _make_engine(temp_db).commit_updates(provider, [])

        assert (
            get_last_seen_id(
                temp_db,
                Provider.FINNHUB,
                Stream.MACRO,
                Scope.GLOBAL,
            )
            == 250
        )

    def test_id_scope_noop_without_last_fetched(self, temp_db):
        """Test id scope noop without last fetched."""
        provider = FinnhubMacroNewsProvider(FinnhubSettings(api_key="test"), ["AAPL"])
        provider.last_fetched_max_id = None

        _make_engine(temp_db).commit_updates(provider, [])

        assert (
            get_last_seen_id(
                temp_db,
                Provider.FINNHUB,
                Stream.MACRO,
                Scope.GLOBAL,
            )
            is None
        )

    def test_social_scope_commits_per_symbol_and_clamps_future(self, temp_db, monkeypatch, caplog):
        """Reddit social watermarks track per symbol and clamp future."""
        settings = RedditSettings(client_id="id", client_secret="secret", user_agent="agent")
        provider = RedditSocialProvider(settings, ["AAPL", "TSLA"])
        fixed_now = datetime(2024, 4, 2, 12, 0, tzinfo=UTC)
        monkeypatch.setattr(watermarks_module, "_utc_now", lambda: fixed_now)
        caplog.set_level("WARNING")

        future_entry = make_social_discussion(
            symbol="AAPL",
            published=fixed_now + timedelta(minutes=5),
        )
        past_entry = make_social_discussion(
            symbol="TSLA",
            source_id="t3_tsla",
            published=fixed_now - timedelta(minutes=10),
        )

        engine = _make_engine(temp_db)
        engine.commit_updates(provider, [future_entry, past_entry])

        aapl_ts = get_last_seen_timestamp(
            temp_db,
            Provider.REDDIT,
            Stream.SOCIAL,
            Scope.SYMBOL,
            symbol="AAPL",
        )
        tsla_ts = get_last_seen_timestamp(
            temp_db,
            Provider.REDDIT,
            Stream.SOCIAL,
            Scope.SYMBOL,
            symbol="TSLA",
        )

        assert aapl_ts == fixed_now + timedelta(seconds=60)
        assert tsla_ts == past_entry.published
        assert "Clamped future watermark provider=REDDIT" in caplog.text

        older_entry = make_social_discussion(
            symbol="AAPL",
            source_id="t3_aapl_old",
            published=fixed_now - timedelta(minutes=30),
        )
        engine.commit_updates(provider, [older_entry])

        assert (
            get_last_seen_timestamp(
                temp_db,
                Provider.REDDIT,
                Stream.SOCIAL,
                Scope.SYMBOL,
                symbol="AAPL",
            )
            == aapl_ts
        )


class TestHelpers:
    """_get_settings and is_macro_stream coverage."""

    def test_get_settings_missing_attribute_raises(self, temp_db):
        """Test get settings missing attribute raises."""
        engine = _make_engine(temp_db)

        class DummyProvider(NewsDataSource):
            async def validate_connection(self) -> bool:  # pragma: no cover - trivial
                return True

            async def fetch_incremental(self, **_kwargs):  # pragma: no cover - trivial
                return []

        provider = DummyProvider("Dummy")

        with pytest.raises(RuntimeError, match="missing required 'settings'"):
            engine._get_settings(provider)

    def test_is_macro_stream_matches_rule(self):
        """Test is macro stream matches rule."""
        finnhub_macro = FinnhubMacroNewsProvider(FinnhubSettings(api_key="test"), ["AAPL"])
        polygon_macro = PolygonMacroNewsProvider(PolygonSettings(api_key="test"), ["SPY"])
        finnhub_company = FinnhubNewsProvider(FinnhubSettings(api_key="test"), ["AAPL"])
        polygon_company = PolygonNewsProvider(PolygonSettings(api_key="test"), ["AAPL"])
        reddit_social = RedditSocialProvider(
            RedditSettings(client_id="id", client_secret="secret", user_agent="agent"),
            ["AAPL"],
        )

        assert is_macro_stream(finnhub_macro) is True
        assert is_macro_stream(polygon_macro) is True
        assert is_macro_stream(finnhub_company) is False
        assert is_macro_stream(polygon_company) is False
        assert is_macro_stream(reddit_social) is False
