"""Contract tests for data provider ABCs and exceptions."""

from collections.abc import Mapping
from datetime import datetime

import pytest

from data.base import DataSource, DataSourceError, NewsDataSource, PriceDataSource, SocialDataSource
from data.models import NewsEntry, PriceData, SocialDiscussion


class TestDataSourceContract:
    """Contract tests for the DataSource abstract base class."""

    def test_source_name_none_raises(self):
        """Test source name none raises."""
        with pytest.raises(ValueError, match="source_name cannot be None"):

            class ConcreteSourceNone(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSourceNone(None)  # type: ignore[reportArgumentType]

    def test_source_name_must_be_string(self):
        """Test source name must be string."""
        with pytest.raises(TypeError, match="source_name must be a string"):

            class ConcreteSourceNotStrA(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSourceNotStrA(123)  # type: ignore[reportArgumentType]

        with pytest.raises(TypeError, match="source_name must be a string"):

            class ConcreteSourceNotStrB(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSourceNotStrB(["list"])  # type: ignore[reportArgumentType]

    def test_source_name_cannot_be_empty(self):
        """Test source name cannot be empty."""
        with pytest.raises(ValueError, match="source_name cannot be empty"):

            class ConcreteSourceEmptyA(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSourceEmptyA("")

        with pytest.raises(ValueError, match="source_name cannot be empty"):

            class ConcreteSourceEmptyB(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSourceEmptyB("   ")

    def test_source_name_length_limit(self):
        """Test source name length limit."""
        long_name = "A" * 101
        with pytest.raises(ValueError, match="source_name too long.*101.*max 100"):

            class ConcreteSourceTooLong(DataSource):
                async def validate_connection(self):
                    return True

            ConcreteSourceTooLong(long_name)

    def test_source_name_normalization(self):
        """Test source name normalization."""

        class ConcreteSourceNormalized(DataSource):
            async def validate_connection(self):
                return True

        source = ConcreteSourceNormalized("Finnhub")
        assert source.source_name == "Finnhub"

        # Max length exactly 100 chars
        source2 = ConcreteSourceNormalized("A" * 100)
        assert source2.source_name == "A" * 100

        source3 = ConcreteSourceNormalized("  Reuters  ")
        assert source3.source_name == "Reuters"

    def test_datasource_is_abstract(self):
        """Test datasource is abstract."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class DataSource"):
            DataSource("Test")  # type: ignore[reportAbstractUsage]


class TestNewsDataSourceContract:
    """Contract tests for the NewsDataSource abstract base class."""

    def test_requires_fetch_incremental(self):
        """Test requires fetch incremental."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*fetch_incremental"):

            class IncompleteNews(NewsDataSource):
                async def validate_connection(self):
                    return True

            IncompleteNews("Test")  # type: ignore[reportAbstractUsage]

    def test_concrete_implementation_satisfies_contract(self):
        """Test concrete implementation satisfies contract."""

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
        """Test requires fetch incremental."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*fetch_incremental"):

            class IncompletePrice(PriceDataSource):
                async def validate_connection(self):
                    return True

            IncompletePrice("Test")  # type: ignore[reportAbstractUsage]

    def test_concrete_implementation_satisfies_contract(self):
        """Test concrete implementation satisfies contract."""

        class ConcretePrice(PriceDataSource):
            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(self) -> list[PriceData]:
                return []

        price_source = ConcretePrice("PriceTest")
        assert price_source.source_name == "PriceTest"


class TestDataSourceErrorContract:
    def test_exception_inheritance(self):
        """Test exception inheritance."""
        assert issubclass(DataSourceError, Exception)

        error = DataSourceError("Test error")
        assert isinstance(error, DataSourceError)
        assert isinstance(error, Exception)


class TestSocialDataSourceContract:
    """Contract tests for the SocialDataSource abstract base class."""

    def test_requires_fetch_incremental(self):
        """SocialDataSource must define fetch_incremental."""
        with pytest.raises(TypeError, match="fetch_incremental"):

            class IncompleteSocial(SocialDataSource):
                async def validate_connection(self):
                    return True

            IncompleteSocial("Test")  # type: ignore[reportAbstractUsage]

    def test_concrete_implementation_satisfies_contract(self):
        """Concrete implementation accepts optional cursors."""

        class ConcreteSocial(SocialDataSource):
            async def validate_connection(self) -> bool:
                return True

            async def fetch_incremental(
                self,
                *,
                since=None,
                symbol_since_map=None,
            ) -> list[SocialDiscussion]:
                assert since is None or isinstance(since, datetime)
                assert symbol_since_map is None or isinstance(symbol_since_map, Mapping)
                return []

        social = ConcreteSocial("SocialTest")
        assert social.source_name == "SocialTest"
