"""Main entry point for the trading bot data poller.

Notes:
    Runs continuous data collection from configured providers at a configurable
    interval (``POLL_INTERVAL`` seconds), storing results in SQLite.
"""

import argparse
import asyncio
import logging
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from config.providers.finnhub import FinnhubSettings
from config.providers.polygon import PolygonSettings
from config.providers.reddit import RedditSettings
from data import DataSourceError, NewsDataSource, PriceDataSource, SocialDataSource
from data.providers.finnhub import (
    FinnhubMacroNewsProvider,
    FinnhubNewsProvider,
    FinnhubPriceProvider,
)
from data.providers.polygon import (
    PolygonMacroNewsProvider,
    PolygonNewsProvider,
)
from data.providers.reddit import RedditSocialProvider
from data.storage import init_database
from utils.logging import setup_logging
from utils.retry import RetryableError
from utils.signals import register_graceful_shutdown
from utils.symbols import parse_symbols
from workflows.poller import DataPoller

PROJECT_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PollerConfig:
    """Configuration for the data poller."""

    db_path: str
    symbols: list[str]
    poll_interval: int
    ui_port: int | None
    finnhub_settings: FinnhubSettings
    polygon_settings: PolygonSettings
    reddit_settings: RedditSettings


def setup_environment() -> None:
    """Load environment and setup logging."""
    load_dotenv(override=True)
    setup_logging()


def build_config(with_viewer: bool) -> PollerConfig:
    """Parse environment variables and build configuration object."""
    # Get database path and ensure directory exists
    db_path = os.getenv("DATABASE_PATH", "data/database/trading_bot.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Get and validate symbols
    symbols_env = os.getenv("SYMBOLS")
    if not symbols_env:
        raise ValueError(
            "SYMBOLS environment variable not set. Please set SYMBOLS in .env "
            "(e.g., SYMBOLS=AAPL,MSFT,TSLA)"
        )

    symbols = parse_symbols(symbols_env, validate=True)
    if not symbols:
        raise ValueError(
            "SYMBOLS environment variable is empty or invalid. Please provide "
            "comma-separated symbols (e.g., SYMBOLS=AAPL,MSFT,TSLA)"
        )

    # Get and validate poll interval
    poll_interval_str = os.getenv("POLL_INTERVAL")
    if not poll_interval_str:
        raise ValueError(
            "POLL_INTERVAL environment variable not set. Please set POLL_INTERVAL "
            "in .env (e.g., POLL_INTERVAL=300)"
        )

    try:
        poll_interval = int(poll_interval_str)
    except ValueError as exc:
        raise ValueError(
            f"Invalid POLL_INTERVAL '{poll_interval_str}', must be an integer. "
            "Please provide a valid integer value (e.g., POLL_INTERVAL=300)"
        ) from exc

    # Get UI port if viewer enabled
    ui_port = None
    if with_viewer:
        port_raw = os.getenv("STREAMLIT_PORT", "8501")
        try:
            ui_port = int(port_raw)
        except ValueError as exc:
            raise ValueError(f"Invalid STREAMLIT_PORT '{port_raw}', must be an integer.") from exc

    # Load Finnhub settings
    try:
        finnhub_settings = FinnhubSettings.from_env()
    except ValueError as exc:
        raise ValueError(
            f"Failed to load Finnhub settings: {exc}. "
            "Please set FINNHUB_API_KEY environment variable"
        ) from exc

    # Load Polygon settings
    try:
        polygon_settings = PolygonSettings.from_env()
    except ValueError as exc:
        raise ValueError(
            f"Failed to load Polygon settings: {exc}. "
            "Please set POLYGON_API_KEY environment variable"
        ) from exc

    # Load Reddit settings
    try:
        reddit_settings = RedditSettings.from_env()
    except ValueError as exc:
        raise ValueError(
            f"Failed to load Reddit settings: {exc}. "
            "Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT"
        ) from exc

    return PollerConfig(
        db_path=db_path,
        symbols=symbols,
        poll_interval=poll_interval,
        ui_port=ui_port,
        finnhub_settings=finnhub_settings,
        polygon_settings=polygon_settings,
        reddit_settings=reddit_settings,
    )


def initialize_database(db_path: str) -> bool:
    """Initialize database and return success status."""
    try:
        init_database(db_path)
        logger.info("Database initialized at %s", db_path)
        return True
    except (RuntimeError, sqlite3.Error, OSError) as exc:
        logger.exception("Failed to initialize database: %s", exc)
        return False


def launch_ui_process(config: PollerConfig) -> subprocess.Popen | None:
    """Launch Streamlit UI when enabled (``-v``), returning the child process.

    Notes:
        Only runs when the UI is enabled (``-v``), which sets ``config.ui_port``.
        The child process receives ``DATABASE_PATH`` and an extended ``PYTHONPATH``.
    """
    if config.ui_port is None:
        return None

    try:
        env = os.environ.copy()
        env["DATABASE_PATH"] = config.db_path
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(PROJECT_ROOT), env.get("PYTHONPATH")])
        )
        ui_process = subprocess.Popen(
            [
                sys.executable,  # use the same Python interpreter as the main process
                "-m",  # run as a script
                "streamlit",
                "run",
                str(PROJECT_ROOT / "ui/app_min.py"),  # path to the Streamlit app file
                "--server.port",
                str(config.ui_port),  # port for the Streamlit server
                "--server.headless",
                "true",  # run without auto-opening a browser window
            ],
            env=env,  # pass modified env so DATABASE_PATH/PYTHONPATH are available
        )
        logger.info("Streamlit UI started at http://localhost:%s", config.ui_port)
        return ui_process
    except FileNotFoundError:
        logger.warning("Streamlit not found. Install with: pip install streamlit")
        logger.warning("Continuing without UI...")
        return None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        logger.warning("Failed to start Streamlit: %s", exc)
        logger.warning("Continuing without UI...")
        return None


async def create_and_validate_providers(
    config: PollerConfig,
) -> tuple[list[NewsDataSource], list[SocialDataSource], list[PriceDataSource]]:
    """Create and validate news and price providers."""
    symbols_csv = ", ".join(config.symbols)
    logger.info("Tracking symbols: %s", symbols_csv)
    logger.info("Poll interval: %s seconds", config.poll_interval)

    # Create Finnhub providers
    company_news_provider = FinnhubNewsProvider(config.finnhub_settings, config.symbols)
    macro_news_provider = FinnhubMacroNewsProvider(config.finnhub_settings, config.symbols)
    finnhub_price_provider = FinnhubPriceProvider(config.finnhub_settings, config.symbols)

    # Create Polygon providers
    polygon_company_news_provider = PolygonNewsProvider(config.polygon_settings, config.symbols)
    polygon_macro_news_provider = PolygonMacroNewsProvider(config.polygon_settings, config.symbols)

    # Create Reddit provider
    reddit_social_provider = RedditSocialProvider(config.reddit_settings, config.symbols)

    # Group providers by type
    news_providers: list[NewsDataSource] = [
        company_news_provider,
        macro_news_provider,
        polygon_company_news_provider,
        polygon_macro_news_provider,
    ]
    social_providers: list[SocialDataSource] = [reddit_social_provider]
    price_providers: list[PriceDataSource] = [finnhub_price_provider]

    # Validate connections
    logger.info("Validating API connections...")
    try:
        providers_to_validate = [
            (company_news_provider, "Finnhub company news"),
            (macro_news_provider, "Finnhub macro news"),
            (finnhub_price_provider, "Finnhub price"),
            (polygon_company_news_provider, "Polygon company news"),
            (polygon_macro_news_provider, "Polygon macro news"),
            (reddit_social_provider, "Reddit social"),
        ]

        results = await asyncio.gather(*[p.validate_connection() for p, _ in providers_to_validate])

        for (_, name), valid in zip(providers_to_validate, results, strict=True):
            if not valid:
                logger.error("Failed to validate %s API connection", name)
                raise ValueError(f"{name} API connection validation failed")
            logger.info("%s API connection validated successfully", name)

    except (DataSourceError, RetryableError, RuntimeError) as exc:
        logger.exception("Connection validation failed: %s", exc)
        raise ValueError(f"Provider validation failed: {exc}") from exc

    return news_providers, social_providers, price_providers


def cleanup_ui_process(ui_process: subprocess.Popen | None) -> None:
    """Terminate Streamlit UI process (graceful then forced).

    Notes:
        Sends terminate(), waits up to 5 seconds, then kill()s as a last resort.
    """
    if ui_process and ui_process.poll() is None:
        ui_process.terminate()
        try:
            ui_process.wait(timeout=5)
            logger.info("Streamlit UI stopped")
        except subprocess.TimeoutExpired as exc:
            logger.warning("Streamlit UI did not stop gracefully; forcing termination: %s", exc)
            ui_process.kill()
        except OSError as exc:
            logger.warning("Error while stopping Streamlit UI: %s", exc)


async def main(with_viewer: bool = False) -> int:
    """Main entry point for the poller.

    Notes:
        When ``with_viewer`` is True, launches the Streamlit web UI alongside
        the poller. Returns an integer exit code (``0`` for success, non-zero
        for failure).
    """
    # Setup environment and logging
    setup_environment()

    # Parse configuration
    try:
        config = build_config(with_viewer)
    except ValueError as e:
        logger.exception("%s", e)
        return 1

    # Initialize database
    if not initialize_database(config.db_path):
        return 1

    # Launch UI process if requested
    ui_process = launch_ui_process(config)

    try:
        # Create and validate providers
        news_providers, social_providers, price_providers = await create_and_validate_providers(
            config
        )
        if not news_providers and not social_providers:
            return 1

        # Create poller
        poller = DataPoller(
            db_path=config.db_path,
            news_providers=news_providers,
            social_providers=social_providers,
            price_providers=price_providers,
            poll_interval=config.poll_interval,
        )

        # Setup signal handlers for graceful shutdown
        register_graceful_shutdown(lambda: poller.stop())

        # Log startup info
        logger.info("=" * 60)
        logger.info("Trading Bot Data Poller Started")
        symbols_csv = ", ".join(config.symbols)
        logger.info("Monitoring %s symbols: %s", len(config.symbols), symbols_csv)
        logger.info("Database: %s", config.db_path)
        logger.info("Poll interval: %ss", config.poll_interval)
        if ui_process:
            logger.info("Web UI: http://localhost:%s", config.ui_port)
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Run the poller
        await poller.run()
        return 0

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        return 0
    except (
        TimeoutError,
        DataSourceError,
        RetryableError,
        RuntimeError,
        ValueError,
        TypeError,
        sqlite3.Error,
        OSError,
    ) as exc:
        logger.exception("Unexpected error in poller: %s", exc)
        return 1
    finally:
        try:
            logger.info("Poller stopped")
            cleanup_ui_process(ui_process)
            logger.info("Shutdown complete")
        except Exception as cleanup_exc:
            logger.exception("Error during cleanup: %s", cleanup_exc)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Trading Bot Data Poller - Made by Marcus Goh")
    parser.add_argument(
        "-v",
        action="store_true",
        help="Launch Streamlit web UI (default port: 8501, configurable via STREAMLIT_PORT)",
    )
    args = parser.parse_args()

    # Run the async main function with parsed arguments
    exit_code = asyncio.run(main(with_viewer=args.v))
    sys.exit(exit_code)
