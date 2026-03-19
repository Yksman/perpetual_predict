"""Daemon mode CLI command for background scheduler execution."""

import argparse
import asyncio
import signal

from perpetual_predict.config import get_settings
from perpetual_predict.scheduler import SchedulerManager, setup_all_jobs
from perpetual_predict.storage.database import Database
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


async def run_daemon(foreground: bool = True) -> None:
    """Run the scheduler daemon.

    Args:
        foreground: Whether to run in foreground mode.
    """
    settings = get_settings()

    logger.info("Starting perpetual_predict daemon...")

    # Initialize database
    database = Database()
    await database.connect()

    # Initialize scheduler with database for run tracking
    scheduler = SchedulerManager(database=database)

    # Register all jobs
    setup_all_jobs(
        scheduler=scheduler,
        database=database,
        collection_interval=settings.scheduler.collection_interval_hours,
        report_interval=settings.scheduler.report_interval_hours,
    )

    # Start scheduler
    await scheduler.start()

    # Setup signal handlers
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logger.info("Daemon started. Press Ctrl+C to stop.")

    # Print registered jobs
    jobs = scheduler.get_jobs()
    print("\nRegistered jobs:")
    for job in jobs:
        print(f"  - {job['id']}: next run at {job['next_run']}")
    print()

    if foreground:
        # Wait for stop signal
        await stop_event.wait()

    # Cleanup
    logger.info("Shutting down daemon...")
    await scheduler.stop(wait=True)
    await database.close()
    logger.info("Daemon stopped")


def run_daemon_command(args: argparse.Namespace) -> int:
    """Run the daemon command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success).
    """
    try:
        asyncio.run(run_daemon(foreground=args.foreground))
        return 0
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
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
        help="Run scheduler daemon for automated data collection and reporting",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        default=True,
        help="Run in foreground mode (default: True)",
    )
    parser.add_argument(
        "--background",
        dest="foreground",
        action="store_false",
        help="Run in background mode (detached)",
    )
    parser.set_defaults(func=run_daemon_command)
