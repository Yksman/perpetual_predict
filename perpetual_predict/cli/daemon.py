"""Daemon mode CLI command for running the scheduler."""

import argparse
import asyncio

from perpetual_predict.scheduler import DataCollectionScheduler
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


def run_daemon(args: argparse.Namespace) -> int:
    """Run the scheduler daemon.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success).
    """
    logger.info("Starting perpetual_predict scheduler daemon...")

    try:
        scheduler = DataCollectionScheduler()

        if args.run_once:
            # Run a single collection and exit (for Cloud Run Jobs)
            logger.info("Running in single-execution mode...")
            results = asyncio.run(scheduler.run_once())

            print("\nCollection Results:")
            print(f"  Candles: {results.get('candles', 0)}")
            print(f"  Funding Rates: {results.get('funding_rates', 0)}")
            print(f"  Open Interests: {results.get('open_interests', 0)}")
            print(f"  Long/Short Ratios: {results.get('long_short_ratios', 0)}")
            print(f"  Fear & Greed: {results.get('fear_greed', 0)}")

            total = sum(results.values())
            print(f"\nTotal records collected: {total}")
        else:
            # Run as persistent daemon
            logger.info("Running in daemon mode...")
            asyncio.run(scheduler.run_forever())

        return 0

    except KeyboardInterrupt:
        logger.info("Shutdown requested via keyboard interrupt")
        return 0
    except Exception as e:
        logger.error(f"Daemon failed: {e}")
        print(f"Error: {e}")
        return 1


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Setup the daemon subcommand parser.

    Args:
        subparsers: Parent subparsers action.
    """
    parser = subparsers.add_parser(
        "daemon",
        help="Run the scheduler daemon for automated data collection",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single collection and exit (useful for Cloud Run Jobs)",
    )
    parser.set_defaults(func=run_daemon)
