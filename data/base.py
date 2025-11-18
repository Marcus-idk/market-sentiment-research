from abc import ABC, abstractmethod
from datetime import datetime

from data.models import NewsEntry, PriceData


class DataSource(ABC):
    """Abstract base class for all data providers (Finnhub, Polygon, Reddit, etc.)."""

    def __init__(self, source_name: str) -> None:
        """Validate and store a human-readable provider name."""
        if source_name is None:
            raise ValueError("source_name cannot be None")
        if not isinstance(source_name, str):
            raise TypeError(f"source_name must be a string, got {type(source_name).__name__}")
        if not source_name.strip():
            raise ValueError("source_name cannot be empty or whitespace only")
        if len(source_name) > 100:
            raise ValueError(f"source_name too long: {len(source_name)} characters (max 100)")

        self.source_name = source_name.strip()

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Test whether the remote service is reachable and credentials work."""


class DataSourceError(Exception):
    """Base exception for data source related errors."""

    pass


class NewsDataSource(DataSource):
    """Abstract base class for data sources that provide news content."""

    @abstractmethod
    async def fetch_incremental(
        self,
        *,
        since: datetime | None = None,
        min_id: int | None = None,
        symbol_since_map: dict[str, datetime | None] | None = None,
    ) -> list[NewsEntry]:
        """Fetch new news items using incremental cursors.

        Notes:
            Implementations may declare only the cursor arguments they support
            (since, min_id, symbol_since_map). Orchestrators must pass only
            relevant cursors to each provider.
        """
        raise NotImplementedError(
            "fetch_incremental must be implemented by subclasses "
            f"(since={since!r}, min_id={min_id!r}, symbol_since_map={symbol_since_map!r})"
        )


class PriceDataSource(DataSource):
    """Abstract base class for data sources that provide price/market data."""

    @abstractmethod
    async def fetch_incremental(self) -> list[PriceData]:
        """Fetch the latest available price data."""

        raise NotImplementedError("fetch_incremental must be implemented by subclasses")
