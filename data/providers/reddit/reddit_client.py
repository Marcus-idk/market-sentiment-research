"""Reddit API client wrapper using PRAW."""

import logging

import praw
from prawcore import exceptions as praw_exceptions

from config.providers.reddit import RedditSettings

logger = logging.getLogger(__name__)


class RedditClient:
    """Minimal Reddit API client wrapper using PRAW."""

    def __init__(self, settings: RedditSettings) -> None:
        """Create a read-only PRAW client."""
        self.settings = settings
        self.reddit = praw.Reddit(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            user_agent=settings.user_agent,
            check_for_async=False,
        )
        self.reddit.read_only = True

    def validate_connection(self) -> bool:
        """Validate OAuth credentials by calling /api/v1/me."""
        try:
            user = self.reddit.user.me()
            return bool(user)
        except praw_exceptions.PrawcoreException as exc:
            logger.warning("RedditClient validation failed: %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001 - defensive catch for unexpected PRAW errors
            logger.warning("RedditClient validation failed: %s", exc)
            return False
