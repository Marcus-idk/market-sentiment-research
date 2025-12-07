"""RedditSocialProvider incremental fetching and parsing."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from config.providers.reddit import RedditSettings
from data.models import SocialDiscussion
from data.providers.reddit.reddit_social import RedditSocialProvider


def _freeze_datetime(monkeypatch, fixed_now: datetime) -> None:
    class FixedDatetime(datetime):  # type: ignore[misc,valid-type]
        @classmethod
        def now(cls, tz=None):
            return fixed_now

        @classmethod
        def fromtimestamp(cls, ts, tz=None):
            return datetime.fromtimestamp(ts, tz)

    monkeypatch.setattr("data.providers.reddit.reddit_social.datetime", FixedDatetime)


@pytest.fixture
def settings() -> RedditSettings:
    return RedditSettings(client_id="id", client_secret="secret", user_agent="agent")


@pytest.fixture(autouse=True)
def immediate_to_thread(monkeypatch):
    async def _immediate(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _immediate)


class FakeComments(list):
    def replace_more(self, limit=0):
        return None


class TestRedditSocialProviderBasics:
    pytestmark = pytest.mark.asyncio

    def test_symbol_normalization_uppercases_and_filters(self, settings):
        provider = RedditSocialProvider(settings, ["aapl", " TSLA ", ""])

        assert provider.symbols == ["AAPL", "TSLA"]

    async def test_validate_connection_delegates_to_client(self, settings):
        provider = RedditSocialProvider(settings, ["AAPL"])
        calls = {"count": 0}

        def fake_validate_connection() -> bool:
            calls["count"] += 1
            return True

        provider.client.validate_connection = fake_validate_connection  # type: ignore[assignment]

        result = await provider.validate_connection()

        assert result is True
        assert calls["count"] == 1


class TestFetchIncremental:
    pytestmark = pytest.mark.asyncio

    async def test_fetch_incremental_empty_symbols_returns_empty(self, settings):
        provider = RedditSocialProvider(settings, [])

        result = await provider.fetch_incremental()

        assert result == []

    async def test_fetch_incremental_bootstrap_uses_week_filter(self, settings, monkeypatch):
        provider = RedditSocialProvider(settings, ["AAPL"])
        fixed_now = datetime(2024, 4, 1, 12, 0, tzinfo=UTC)
        _freeze_datetime(monkeypatch, fixed_now)
        captured: dict[str, object] = {}

        def fake_fetch(symbol, start_time, time_filter):
            captured.update(
                {"symbol": symbol, "start_time": start_time, "time_filter": time_filter}
            )
            return []

        provider._fetch_symbol = fake_fetch  # type: ignore[assignment]

        await provider.fetch_incremental()

        expected_start = fixed_now - timedelta(days=settings.social_news_first_run_days)
        assert captured["start_time"] == expected_start
        assert captured["time_filter"] == settings.bootstrap_time_filter

    async def test_fetch_incremental_cursor_uses_hour_with_overlap(self, settings, monkeypatch):
        provider = RedditSocialProvider(settings, ["AAPL"])
        fixed_now = datetime(2024, 4, 1, 12, 0, tzinfo=UTC)
        _freeze_datetime(monkeypatch, fixed_now)
        captured: dict[str, object] = {}
        cursor_time = datetime(2024, 4, 1, 11, 0, tzinfo=UTC)

        def fake_fetch(symbol, start_time, time_filter):
            captured.update(
                {"symbol": symbol, "start_time": start_time, "time_filter": time_filter}
            )
            return []

        provider._fetch_symbol = fake_fetch  # type: ignore[assignment]

        await provider.fetch_incremental(symbol_since_map={"AAPL": cursor_time})

        expected_start = cursor_time - timedelta(minutes=settings.social_news_overlap_minutes)
        assert captured["start_time"] == expected_start
        assert captured["time_filter"] == settings.incremental_time_filter

    def test_resolve_symbol_cursor_prefers_symbol_map_over_global(self, settings):
        provider = RedditSocialProvider(settings, ["AAPL"])
        symbol_map = {"AAPL": datetime(2024, 4, 1, 10, 0, tzinfo=UTC)}
        global_since = datetime(2024, 4, 1, 9, 0, tzinfo=UTC)

        result = provider._resolve_symbol_cursor("AAPL", symbol_map, global_since)

        assert result == symbol_map["AAPL"]

    async def test_fetch_incremental_praw_error_skips_symbol_not_all(self, settings, monkeypatch):
        provider = RedditSocialProvider(settings, ["AAPL", "TSLA"])
        fixed_now = datetime(2024, 4, 1, 12, 0, tzinfo=UTC)
        _freeze_datetime(monkeypatch, fixed_now)
        dummy_exc = type("DummyPrawExc", (Exception,), {})
        monkeypatch.setattr(
            "data.providers.reddit.reddit_social.praw_exceptions.PrawcoreException", dummy_exc
        )

        def fetch_symbol(symbol, *_args, **_kwargs):
            if symbol == "AAPL":
                raise dummy_exc("fail")
            return [
                SocialDiscussion(
                    "reddit",
                    f"t3_{symbol}",
                    symbol,
                    "stocks",
                    "Title",
                    "https://reddit.com",
                    fixed_now,
                )
            ]

        provider._fetch_symbol = fetch_symbol  # type: ignore[assignment]

        result = await provider.fetch_incremental()

        assert len(result) == 1
        assert result[0].symbol == "TSLA"


class TestParseSubmission:
    def _provider(self, settings) -> RedditSocialProvider:
        return RedditSocialProvider(settings, ["AAPL"])

    def test_parse_submission_valid_returns_discussion(self, settings, monkeypatch):
        provider = self._provider(settings)
        start_time = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
        submission = SimpleNamespace(
            created_utc=1704100800.0,  # 2024-01-01 10:00 UTC
            title="Test Title",
            permalink="/r/stocks/comments/abc",
            subreddit=SimpleNamespace(display_name="stocks"),
            name="t3_abc",
            selftext="Body",
            comments=FakeComments(),
        )

        discussion = provider._parse_submission(submission, "AAPL", start_time)

        assert discussion is not None
        assert discussion.source_id == "t3_abc"
        assert discussion.symbol == "AAPL"
        assert discussion.community == "stocks"
        assert discussion.title == "Test Title"
        assert discussion.url == "https://www.reddit.com/r/stocks/comments/abc"

    @pytest.mark.parametrize(
        "submission",
        [
            SimpleNamespace(
                created_utc=None,
                title="Title",
                permalink="/r/stocks/1",
                subreddit=SimpleNamespace(display_name="stocks"),
                name="t3_id",
                comments=FakeComments(),
            ),
            SimpleNamespace(
                created_utc=1704100800.0,
                title="",
                permalink="/r/stocks/1",
                subreddit=SimpleNamespace(display_name="stocks"),
                name="t3_id",
                comments=FakeComments(),
            ),
            SimpleNamespace(
                created_utc=1704100800.0,
                title="Title",
                permalink="",
                url="not-http",
                subreddit=SimpleNamespace(display_name="stocks"),
                name="t3_id",
                comments=FakeComments(),
            ),
        ],
    )
    def test_parse_submission_invalid_returns_none(self, settings, submission):
        provider = self._provider(settings)
        start_time = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        assert provider._parse_submission(submission, "AAPL", start_time) is None

    def test_parse_submission_returns_none_when_before_start(self, settings):
        provider = self._provider(settings)
        start_time = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        submission = SimpleNamespace(
            created_utc=1704100800.0,
            title="Title",
            permalink="/r/stocks/1",
            subreddit=SimpleNamespace(display_name="stocks"),
            name="t3_id",
            comments=FakeComments(),
        )

        result = provider._parse_submission(submission, "AAPL", start_time)

        assert result is None


class TestBuildContent:
    def test_build_content_combines_selftext_and_comments(self, settings):
        provider = RedditSocialProvider(settings, ["AAPL"])
        comments = FakeComments(
            [
                SimpleNamespace(body="First"),
                SimpleNamespace(body="Second"),
                SimpleNamespace(body=""),
            ]
        )
        submission = SimpleNamespace(selftext="Body", comments=comments)

        content = provider._build_content(submission)

        assert content == "Post: Body\n\nComments:\n\nFirst\n\nSecond"

    def test_build_content_empty_returns_none(self, settings, caplog):
        provider = RedditSocialProvider(settings, ["AAPL"])
        submission = SimpleNamespace(selftext="", comments=FakeComments())

        caplog.set_level("DEBUG")
        content = provider._build_content(submission)

        assert content is None
