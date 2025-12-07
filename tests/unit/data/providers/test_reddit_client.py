"""RedditClient wiring and validation behavior."""

import types

from config.providers.reddit import RedditSettings
from data.providers.reddit.reddit_client import RedditClient


class TestRedditClient:
    """Covers RedditClient init and validate_connection."""

    def test_init_sets_read_only_and_creds(self, monkeypatch):
        """praw.Reddit called with provided creds and read_only enabled."""
        captured = {}

        class DummyReddit:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self.read_only = False
                self.user = types.SimpleNamespace(me=lambda: "ok")

        monkeypatch.setattr(
            "data.providers.reddit.reddit_client.praw.Reddit",
            lambda **kwargs: DummyReddit(**kwargs),
        )

        settings = RedditSettings(client_id="id", client_secret="secret", user_agent="agent")

        client = RedditClient(settings)

        assert captured == {
            "client_id": "id",
            "client_secret": "secret",
            "user_agent": "agent",
            "check_for_async": False,
        }
        assert client.reddit.read_only is True

    def test_validate_connection_success(self, monkeypatch):
        """Returns True when reddit.user.me is truthy."""
        settings = RedditSettings(client_id="id", client_secret="secret", user_agent="agent")
        client = RedditClient(settings)
        client.reddit = types.SimpleNamespace(user=types.SimpleNamespace(me=lambda: "ok"))  # type: ignore[assignment]

        assert client.validate_connection() is True

    def test_validate_connection_praw_error_logs_and_returns_false(self, caplog, monkeypatch):
        """PrawcoreException returns False and logs warning."""
        settings = RedditSettings(client_id="id", client_secret="secret", user_agent="agent")
        client = RedditClient(settings)
        dummy_exc = type("DummyPrawExc", (Exception,), {})
        monkeypatch.setattr(
            "data.providers.reddit.reddit_client.praw_exceptions.PrawcoreException", dummy_exc
        )
        client.reddit = types.SimpleNamespace(  # type: ignore[assignment]
            user=types.SimpleNamespace(me=lambda: (_ for _ in ()).throw(dummy_exc()))  # type: ignore[arg-type]
        )

        caplog.set_level("WARNING")
        assert client.validate_connection() is False
        assert "RedditClient validation failed" in caplog.text

    def test_validate_connection_generic_error_returns_false(self, caplog):
        """Generic errors also return False and warn."""
        settings = RedditSettings(client_id="id", client_secret="secret", user_agent="agent")
        client = RedditClient(settings)

        def boom():
            raise RuntimeError("oops")

        client.reddit = types.SimpleNamespace(user=types.SimpleNamespace(me=boom))  # type: ignore[assignment]

        caplog.set_level("WARNING")
        assert client.validate_connection() is False
        assert "RedditClient validation failed" in caplog.text
