"""Contract tests for data provider ABCs and exceptions."""

from datetime import datetime

import pytest

from data.base import DataSource, DataSourceError, NewsDataSource, PriceDataSource
from data.models import NewsEntry, PriceData


class TestDataSourceContract:
    """Contract tests for the DataSource abstract base class."""

    def test_source_name_none_raises(self):
        with pytest.raises(ValueError, match="source_name cannot be None"):

            class ConcreteSource(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSource(None)

    def test_source_name_must_be_string(self):
        with pytest.raises(TypeError, match="source_name must be a string"):

            class ConcreteSource(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSource(123)

        with pytest.raises(TypeError, match="source_name must be a string"):

            class ConcreteSource(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSource(["list"])

    def test_source_name_cannot_be_empty(self):
        with pytest.raises(ValueError, match="source_name cannot be empty"):

            class ConcreteSource(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSource("")

        with pytest.raises(ValueError, match="source_name cannot be empty"):

            class ConcreteSource(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSource("   ")

    def test_source_name_length_limit(self):
        long_name = "A" * 101
        with pytest.raises(ValueError, match="source_name too long.*101.*max 100"):

            class ConcreteSource(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSource(long_name)

    def test_source_name_normalization(self):
        class ConcreteSource(DataSource):
            async def validate_connection(self):
                return True

        source = ConcreteSource("Finnhub")
        assert source.source_name == "Finnhub"

        # Max length exactly 100 chars
        source2 = ConcreteSource("A" * 100)
        assert source2.source_name == "A" * 100

        source3 = ConcreteSource("  Reuters  ")
        assert source3.source_name == "Reuters"

    def test_datasource_is_abstract(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class DataSource"):
            DataSource("Test")


class TestNewsDataSourceContract:
    """Contract tests for the NewsDataSource abstract base class."""

    def test_requires_fetch_incremental(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*fetch_incremental"):

            class IncompleteNews(NewsDataSource):
                async def validate_connection(self):
                    return True

            IncompleteNews("Test")

    def test_concrete_implementation_satisfies_contract(self):
        class ConcreteNews(NewsDataSource):
            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(
                self,
                *,
                since: datetime | None = None,
                min_id: int | None = None,
            ) -> list[NewsEntry]:
                assert since is None or isinstance(since, datetime)
                assert min_id is None or isinstance(min_id, int)
                return []

        news_source = ConcreteNews("NewsTest")
        assert news_source.source_name == "NewsTest"


class TestPriceDataSourceContract:
    """Contract tests for the PriceDataSource abstract base class."""

    def test_requires_fetch_incremental(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*fetch_incremental"):

            class IncompletePrice(PriceDataSource):
                async def validate_connection(self):
                    return True

            IncompletePrice("Test")

    def test_concrete_implementation_satisfies_contract(self):
        class ConcretePrice(PriceDataSource):
            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(
                self,
                *,
                since: datetime | None = None,
            ) -> list[PriceData]:
                assert since is None or isinstance(since, datetime)
                return []

        price_source = ConcretePrice("PriceTest")
        assert price_source.source_name == "PriceTest"


class TestDataSourceErrorContract:
    def test_exception_inheritance(self):
        assert issubclass(DataSourceError, Exception)

        error = DataSourceError("Test error")
        assert isinstance(error, DataSourceError)
        assert isinstance(error, Exception)
