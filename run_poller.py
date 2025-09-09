"""
Main entry point for the trading bot data poller.

Runs continuous data collection from Finnhub every 5 minutes,
storing results in SQLite database.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from config.providers.finnhub import FinnhubSettings
from data.poller import DataPoller
from data.providers.finnhub import FinnhubNewsProvider, FinnhubPriceProvider
from data.storage import init_database
from utils.logging import setup_logging
from utils.signals import register_graceful_shutdown

logger = logging.getLogger(__name__)

async def main() -> int:
    """
    Main entry point for the poller.
    
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
        price_providers=[price_provider]    # add more providers here
    )
    
    # Setup signal handlers for graceful shutdown
    register_graceful_shutdown(lambda: poller.stop())
    
    # Run the poller
    logger.info("=" * 60)
    logger.info("Trading Bot Data Poller Started")
    logger.info(f"Monitoring {len(symbols)} symbols: {', '.join(symbols)}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Poll interval: {DataPoller.POLL_INTERVAL}s")
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
    
    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)