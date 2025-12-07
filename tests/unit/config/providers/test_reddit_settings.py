"""RedditSettings provider-specific env loading tests."""

import pytest

from config.providers.reddit import RedditSettings
from config.retry import DEFAULT_DATA_RETRY


class TestRedditSettings:
    """RedditSettings.from_env behavior."""

    def test_from_env_success(self, monkeypatch):
        """Loads all required fields and keeps default retry config."""
        monkeypatch.setenv("REDDIT_CLIENT_ID", "client")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
        monkeypatch.setenv("REDDIT_USER_AGENT", "agent")

        settings = RedditSettings.from_env()

        assert settings.client_id == "client"
        assert settings.client_secret == "secret"
        assert settings.user_agent == "agent"
        assert settings.retry_config == DEFAULT_DATA_RETRY

    def test_from_env_missing_client_id(self, monkeypatch):
        """Missing client id raises ValueError."""
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
        monkeypatch.setenv("REDDIT_USER_AGENT", "agent")

        with pytest.raises(ValueError, match="REDDIT_CLIENT_ID environment variable not found"):
            RedditSettings.from_env()

    def test_from_env_missing_client_secret(self, monkeypatch):
        """Missing client secret raises ValueError."""
        monkeypatch.setenv("REDDIT_CLIENT_ID", "client")
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("REDDIT_USER_AGENT", "agent")

        with pytest.raises(ValueError, match="REDDIT_CLIENT_SECRET environment variable not found"):
            RedditSettings.from_env()

    def test_from_env_missing_user_agent(self, monkeypatch):
        """Missing user agent raises ValueError."""
        monkeypatch.setenv("REDDIT_CLIENT_ID", "client")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
        monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

        with pytest.raises(ValueError, match="REDDIT_USER_AGENT environment variable not found"):
            RedditSettings.from_env()

    def test_from_env_strips_whitespace(self, monkeypatch):
        """Whitespace around values is stripped."""
        monkeypatch.setenv("REDDIT_CLIENT_ID", "  client  ")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "\tsecret\n")
        monkeypatch.setenv("REDDIT_USER_AGENT", " agent ")

        settings = RedditSettings.from_env()

        assert settings.client_id == "client"
        assert settings.client_secret == "secret"
        assert settings.user_agent == "agent"
