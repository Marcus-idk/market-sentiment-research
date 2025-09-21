"""
Main entry point for the trading bot data poller.

Runs continuous data collection from Finnhub every 5 minutes,
storing results in SQLite database.
"""

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from config.providers.finnhub import FinnhubSettings
from workflows.poller import DataPoller
from data.providers.finnhub import FinnhubNewsProvider, FinnhubPriceProvider
from data.storage import init_database
from utils.logging import setup_logging
from utils.signals import register_graceful_shutdown

logger = logging.getLogger(__name__)

async def main(with_viewer: bool = False) -> int:
    """
    Main entry point for the poller.
    
    Args:
        with_viewer: If True, launch Datasette web viewer alongside poller
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Load environment variables
    load_dotenv(override=True)
    
    # Configure logging
    setup_logging()
    
    # Get database path from environment or use default
    db_path = os.getenv("DATABASE_PATH", "data/trading_bot.db")
    
    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    try:
        init_database(db_path)
        logger.info(f"Database initialized at {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1
    
    # Launch Datasette viewer if requested
    datasette_process = None
    datasette_port = os.getenv("DATASETTE_PORT", "8001")
    
    if with_viewer:
        try:
            datasette_process = subprocess.Popen(
                ["datasette", db_path, "--port", datasette_port],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info(f"Datasette viewer started at http://localhost:{datasette_port}")
            logger.info("Open your browser and navigate to the URL above to view data")
        except FileNotFoundError:
            logger.warning("Datasette not found. Install with: pip install datasette")
            logger.warning("Continuing without viewer...")
        except Exception as e:
            logger.warning(f"Failed to start Datasette: {e}")
            logger.warning("Continuing without viewer...")
    
    # Create Finnhub settings and providers
    try:
        settings = FinnhubSettings.from_env()
        logger.info("Finnhub API key loaded from environment")
    except ValueError as e:
        logger.error(f"Failed to load Finnhub settings: {e}")
        logger.error("Please set FINNHUB_API_KEY environment variable")
        return 1
    
    # Get symbols from environment (required, no defaults)
    symbols_env = os.getenv("SYMBOLS")
    if not symbols_env:
        logger.error("SYMBOLS environment variable not set")
        logger.error("Please set SYMBOLS in .env (e.g., SYMBOLS=AAPL,MSFT,TSLA)")
        return 1
    
    # Parse and clean symbols
    symbols = [s.strip().upper() for s in symbols_env.split(",") if s.strip()]
    if not symbols:
        logger.error("SYMBOLS environment variable is empty or invalid")
        logger.error("Please provide comma-separated symbols (e.g., SYMBOLS=AAPL,MSFT,TSLA)")
        return 1
    
    logger.info(f"Tracking symbols: {', '.join(symbols)}")
    
    # Get polling interval from environment (required, no defaults)
    poll_interval_str = os.getenv("POLL_INTERVAL")
    if not poll_interval_str:
        logger.error("POLL_INTERVAL environment variable not set")
        logger.error("Please set POLL_INTERVAL in .env (e.g., POLL_INTERVAL=300)")
        return 1
    
    try:
        poll_interval = int(poll_interval_str)
    except ValueError:
        logger.error(f"Invalid POLL_INTERVAL '{poll_interval_str}', must be an integer")
        logger.error("Please provide a valid integer value (e.g., POLL_INTERVAL=300)")
        return 1
    
    logger.info(f"Poll interval: {poll_interval} seconds")
    
    # Create providers with the configured symbols
    news_provider = FinnhubNewsProvider(settings, symbols)
    price_provider = FinnhubPriceProvider(settings, symbols)
    
    # Validate connections
    logger.info("Validating API connections...")
    try:
        news_valid = await news_provider.validate_connection()
        if not news_valid:
            logger.error("Failed to validate Finnhub news API connection")
            return 1
        logger.info("News API connection validated successfully")
        
        price_valid = await price_provider.validate_connection()
        if not price_valid:
            logger.error("Failed to validate Finnhub price API connection")
            return 1
        logger.info("Price API connection validated successfully")
        
    except Exception as e:
        logger.error(f"Connection validation failed: {e}")
        return 1
    
    # Create poller with lists of providers
    poller = DataPoller(
        db_path=db_path,
        news_providers=[news_provider],
        price_providers=[price_provider],    # add more providers here
        poll_interval=poll_interval
    )
    
    # Setup signal handlers for graceful shutdown
    register_graceful_shutdown(lambda: poller.stop())
    
    # Run the poller
    logger.info("=" * 60)
    logger.info("Trading Bot Data Poller Started")
    logger.info(f"Monitoring {len(symbols)} symbols: {', '.join(symbols)}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Poll interval: {poll_interval}s")
    if datasette_process:
        logger.info(f"Web viewer: http://localhost:{datasette_port}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    
    try:
        await poller.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error in poller: {e}", exc_info=True)
        return 1
    finally:
        logger.info("Poller stopped")
        
        # Clean up Datasette process if running
        if datasette_process:
            try:
                datasette_process.terminate()
                datasette_process.wait(timeout=5)
                logger.info("Datasette viewer stopped")
            except Exception as e:
                logger.warning(f"Error stopping Datasette: {e}", exc_info=True)
                try:
                    datasette_process.kill()
                    datasette_process.wait(timeout=3)
                except Exception as e2:
                    logger.error(f"Datasette kill() failed: {e2}", exc_info=True)
    
    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Trading Bot Data Poller - Collects market data every 5 minutes"
    )
    parser.add_argument(
        "-v",
        action="store_true",
        help="Launch Datasette web viewer (default port: 8001, configurable via DATASETTE_PORT)"
    )
    args = parser.parse_args()
    
    # Run the async main function with parsed arguments
    exit_code = asyncio.run(main(with_viewer=args.v))
    sys.exit(exit_code)