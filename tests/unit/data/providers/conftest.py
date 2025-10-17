"""Common fixtures for data provider contract tests."""

from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

import pytest

from config.providers.finnhub import FinnhubSettings
from config.providers.polygon import PolygonSettings
from config.retry import DataRetryConfig
from data import NewsDataSource, PriceDataSource
from data.storage.storage_utils import _datetime_to_iso
from data.providers.finnhub import (
    FinnhubMacroNewsProvider,
    FinnhubNewsProvider,
    FinnhubPriceProvider,
)
from data.providers.finnhub.finnhub_client import FinnhubClient
from data.providers.polygon import (
    PolygonMacroNewsProvider,
    PolygonNewsProvider,
)
from data.providers.polygon.polygon_client import PolygonClient


@dataclass(slots=True)
class CompanyProviderSpec:
    """Specification for company news provider contract tests."""

    name: str
    endpoint: str
    default_symbols: list[str]
    provider_factory: Callable[[list[str]], NewsDataSource]
    symbol_param_name: str
    article_factory: Callable[..., dict[str, Any]]

    def make_provider(self, symbols: list[str] | None = None) -> NewsDataSource:
        symbols_to_use = symbols if symbols is not None else list(self.default_symbols)
        return self.provider_factory(symbols_to_use)

    def wrap_response(self, payload: list[dict[str, Any]]) -> Any:
        """Wrap provider payload to match API response shape."""
        if "polygon" in self.name:
            return {"results": payload}
        return payload

    def malformed(self, *, as_type: type[Any]) -> Any:
        if as_type is dict:
            if "polygon" in self.name:
                return {"results": "not-a-list"}
            return {"unexpected": "structure"}
        return "unexpected"


@dataclass(slots=True)
class MacroProviderSpec:
    """Specification for macro news provider contract tests."""

    name: str
    endpoint: str
    default_symbols: list[str]
    provider_factory: Callable[[list[str]], NewsDataSource]
    article_factory: Callable[..., dict[str, Any]]

    def make_provider(self, symbols: list[str] | None = None) -> NewsDataSource:
        symbols_to_use = symbols if symbols is not None else list(self.default_symbols)
        return self.provider_factory(symbols_to_use)

    def wrap_response(self, payload: list[dict[str, Any]]) -> Any:
        """Wrap provider payload to match API response shape."""
        if "polygon" in self.name:
            return {"results": payload}
        return payload

    def malformed(self, *, as_type: type[Any]) -> Any:
        if as_type is dict:
            if "polygon" in self.name:
                return {"results": "not-a-list"}
            return {"unexpected": "structure"}
        return "unexpected"


@dataclass(slots=True)
class PriceProviderSpec:
    """Specification for price provider contract tests."""

    name: str
    endpoint: str
    default_symbols: list[str]
    provider_factory: Callable[[list[str]], PriceDataSource]

    def make_provider(self, symbols: list[str] | None = None) -> PriceDataSource:
        symbols_to_use = symbols if symbols is not None else list(self.default_symbols)
        return self.provider_factory(symbols_to_use)

    @staticmethod
    def quote(
        *,
        price: Any = Decimal("150.0"),
        timestamp: int | None = None,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if price is not None:
            data["c"] = price
        if timestamp is not None:
            data["t"] = timestamp
        else:
            data["t"] = int(datetime.now(timezone.utc).timestamp())
        if extras:
            data.update(extras)
        return data

    @staticmethod
    def malformed(*, as_type: type[Any]) -> Any:
        if as_type is dict:
            return {"unexpected": "structure"}
        return "unexpected"


@dataclass(slots=True)
class ClientSpec:
    """Specification for client contract tests."""

    name: str
    module_path: str
    client_factory: Callable[[], Any]
    base_url: str
    sample_path: str
    sample_params: dict[str, Any]
    auth_param: str
    api_key: str
    retry_config: DataRetryConfig
    validation_path: str
    validation_params: dict[str, Any] | None

    def make_client(self) -> Any:
        return self.client_factory()


def _finnhub_settings() -> FinnhubSettings:
    return FinnhubSettings(api_key="test_key")


def _polygon_settings() -> PolygonSettings:
    return PolygonSettings(api_key="test_key")


@pytest.fixture(params=["finnhub", "polygon"])
def provider_spec_company(request: pytest.FixtureRequest) -> CompanyProviderSpec:
    if request.param == "finnhub":
        def finnhub_company_article_factory(**kwargs) -> dict[str, Any]:
            article: dict[str, Any] = {
                "headline": kwargs.get("headline", "Market rally"),
                "url": kwargs.get("url", "https://example.com/news"),
                "datetime": kwargs.get("epoch", int(datetime.now(timezone.utc).timestamp())),
            }
            if "source" in kwargs and kwargs["source"] is not None:
                article["source"] = kwargs["source"]
            else:
                article["source"] = "Finnhub"
            if "summary" in kwargs and kwargs["summary"] is not None:
                article["summary"] = kwargs["summary"]
            else:
                article["summary"] = "Stocks up today"
            return article

        return CompanyProviderSpec(
            name="finnhub",
            endpoint="/company-news",
            default_symbols=["AAPL"],
            provider_factory=lambda symbols: FinnhubNewsProvider(_finnhub_settings(), symbols),
            symbol_param_name="symbol",
            article_factory=finnhub_company_article_factory,
        )
    else:
        def polygon_company_article_factory(**kwargs) -> dict[str, Any]:
            epoch = kwargs.get("epoch", int(datetime.now(timezone.utc).timestamp()))
            published_utc = _datetime_to_iso(datetime.fromtimestamp(epoch, tz=timezone.utc))
            article: dict[str, Any] = {
                "title": kwargs.get("headline", "Market rally"),
                "article_url": kwargs.get("url", "https://example.com/news"),
                "published_utc": published_utc,
                "publisher": {"name": kwargs.get("source", "Polygon")},
                "description": kwargs.get("summary", "Stocks up today"),
            }
            return article

        return CompanyProviderSpec(
            name="polygon",
            endpoint="/v2/reference/news",
            default_symbols=["AAPL"],
            provider_factory=lambda symbols: PolygonNewsProvider(_polygon_settings(), symbols),
            symbol_param_name="ticker",
            article_factory=polygon_company_article_factory,
        )


@pytest.fixture(params=["finnhub", "polygon"])
def provider_spec_macro(request: pytest.FixtureRequest) -> MacroProviderSpec:
    if request.param == "finnhub":
        def finnhub_article_factory(symbols: str | list[str] = "AAPL", **kwargs) -> dict[str, Any]:
            related_str = symbols if isinstance(symbols, str) else ",".join(symbols)
            article: dict[str, Any] = {
                "id": kwargs.get("article_id", 101),
                "headline": kwargs.get("headline", "Macro update"),
                "url": kwargs.get("url", "https://example.com/macro"),
                "datetime": kwargs.get("epoch", int(datetime.now(timezone.utc).timestamp())),
                "related": related_str,
            }
            if "source" in kwargs and kwargs["source"] is not None:
                article["source"] = kwargs["source"]
            else:
                article["source"] = "Finnhub"
            if "summary" in kwargs and kwargs["summary"] is not None:
                article["summary"] = kwargs["summary"]
            else:
                article["summary"] = "Macro summary"
            return article

        return MacroProviderSpec(
            name="finnhub_macro",
            endpoint="/news",
            default_symbols=["AAPL"],
            provider_factory=lambda symbols: FinnhubMacroNewsProvider(_finnhub_settings(), symbols),
            article_factory=finnhub_article_factory,
        )
    else:
        def polygon_article_factory(symbols: str | list[str] = "AAPL", **kwargs) -> dict[str, Any]:
            tickers_list = symbols.split(",") if isinstance(symbols, str) else list(symbols)
            if tickers_list == [""]:
                tickers_list = []
            epoch = kwargs.get("epoch", int(datetime.now(timezone.utc).timestamp()))
            published_utc = _datetime_to_iso(datetime.fromtimestamp(epoch, tz=timezone.utc))
            article: dict[str, Any] = {
                "id": kwargs.get("article_id", 101),
                "title": kwargs.get("headline", "Macro update"),
                "article_url": kwargs.get("url", "https://example.com/macro"),
                "published_utc": published_utc,
                "tickers": tickers_list,
                "publisher": {"name": kwargs.get("source", "Polygon")},
                "description": kwargs.get("summary", "Macro summary"),
            }
            return article

        return MacroProviderSpec(
            name="polygon_macro",
            endpoint="/v2/reference/news",
            default_symbols=["AAPL"],
            provider_factory=lambda symbols: PolygonMacroNewsProvider(_polygon_settings(), symbols),
            article_factory=polygon_article_factory,
        )


@pytest.fixture
def provider_spec_prices() -> PriceProviderSpec:
    return PriceProviderSpec(
        name="finnhub_prices",
        endpoint="/quote",
        default_symbols=["AAPL"],
        provider_factory=lambda symbols: FinnhubPriceProvider(_finnhub_settings(), symbols),
    )


@pytest.fixture(params=("finnhub_client", "polygon_client"))
def client_spec(request: pytest.FixtureRequest) -> ClientSpec:
    if request.param == "finnhub_client":
        api_key = "finnhub_test_key"
        settings = FinnhubSettings(api_key=api_key)
        return ClientSpec(
            name="finnhub_client",
            module_path="data.providers.finnhub.finnhub_client",
            client_factory=lambda: FinnhubClient(settings),
            base_url=settings.base_url,
            sample_path="/company-news",
            sample_params={"symbol": "AAPL"},
            auth_param="token",
            api_key=api_key,
            retry_config=settings.retry_config,
            validation_path="/quote",
            validation_params={"symbol": "SPY"},
        )

    api_key = "polygon_test_key"
    settings = PolygonSettings(api_key=api_key)
    return ClientSpec(
        name="polygon_client",
        module_path="data.providers.polygon.polygon_client",
        client_factory=lambda: PolygonClient(settings),
        base_url=settings.base_url,
        sample_path="/v2/reference/news",
        sample_params={"ticker": "AAPL"},
        auth_param="apiKey",
        api_key=api_key,
        retry_config=settings.retry_config,
        validation_path="/v1/marketstatus/now",
        validation_params=None,
    )
