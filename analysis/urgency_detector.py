"""Urgency detection helpers for news and social entries."""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from data.models import NewsEntry, SocialDiscussion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UrgencyInput:
    """Normalized text + metadata for urgency scoring."""

    kind: Literal["news", "social"]
    symbol: str
    title: str
    body: str
    url: str | None


def detect_news_urgency(news_entries: Sequence[NewsEntry]) -> list[NewsEntry]:
    """Detect urgent news items. Stub: returns empty."""
    inputs = _build_news_inputs(news_entries)
    _log_stub_stats(inputs, "news")
    return []


def detect_social_urgency(social_items: Sequence[SocialDiscussion]) -> list[SocialDiscussion]:
    """Detect urgent social discussions. Stub: returns empty."""
    inputs = _build_social_inputs(social_items)
    _log_stub_stats(inputs, "social")
    return []


def _build_news_inputs(entries: Iterable[NewsEntry]) -> list[UrgencyInput]:
    """Normalize news entries into urgency-scoring inputs."""
    inputs: list[UrgencyInput] = []
    for entry in entries:
        title = entry.headline.strip()
        body_parts = []
        if entry.content:
            body_parts.append(entry.content.strip())
        body = "\n\n".join(p for p in body_parts if p)
        inputs.append(
            UrgencyInput(
                kind="news",
                symbol=entry.symbol,
                title=title,
                body=body,
                url=entry.url,
            )
        )
    return inputs


def _build_social_inputs(items: Iterable[SocialDiscussion]) -> list[UrgencyInput]:
    """Normalize social discussions into urgency-scoring inputs."""
    inputs: list[UrgencyInput] = []
    for discussion in items:
        title = discussion.title.strip()
        body_parts = []
        if discussion.content:
            body_parts.append(discussion.content.strip())
        body = "\n\n".join(p for p in body_parts if p)
        inputs.append(
            UrgencyInput(
                kind="social",
                symbol=discussion.symbol,
                title=title,
                body=body,
                url=discussion.url,
            )
        )
    return inputs


def _log_stub_stats(inputs: Sequence[UrgencyInput], stream: str) -> None:
    """Log basic stats for stub urgency detection."""
    if not inputs:
        logger.debug("No %s items to analyze for urgency (stub)", stream)
        return
    total_chars = sum(len(i.title) + len(i.body) for i in inputs)
    logger.debug(
        "Analyzed %s %s items for urgency (stub) — text_len=%s",
        len(inputs),
        stream,
        total_chars,
    )
