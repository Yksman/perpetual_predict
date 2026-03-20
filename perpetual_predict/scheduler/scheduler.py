"""Core scheduler implementation using APScheduler."""

import asyncio
import signal
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from perpetual_predict.config import get_settings
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.scheduler.jobs import collection_job
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class DataCollectionScheduler:
    """Async scheduler for data collection jobs."""

    def __init__(self, health_file: Path | None = None) -> None:
        """Initialize the scheduler.

        Args:
            health_file: Path to write health status. Defaults to data/scheduler_status.json.
        """
        self.settings = get_settings()
        self._scheduler: AsyncIOScheduler | None = None
        self._health_status = HealthStatus()
        self._shutdown_event = asyncio.Event()
        self._health_file = health_file or Path("data/scheduler_status.json")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown_signal, sig)

    def _handle_shutdown_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signal.

        Args:
            sig: The signal received.
        """
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")
        self._shutdown_event.set()

    async def _run_collection_job(self) -> None:
        """Wrapper to run collection job and update health status."""
        try:
            await collection_job(self._health_status)
        finally:
            self._health_status.to_file(self._health_file)

    async def run_once(self) -> dict[str, int]:
        """Run a single collection and exit.

        This mode is designed for GitHub Actions and cron jobs.

        Returns:
            Dictionary with counts of collected records.
        """
        logger.info("Running single collection (--run-once mode)...")
        self._health_status.is_running = True
        self._health_status.to_file(self._health_file)

        try:
            results = await collection_job(self._health_status)
            return results
        finally:
            self._health_status.is_running = False
            self._health_status.to_file(self._health_file)

    async def start(self) -> None:
        """Start the scheduler with configured jobs."""
        settings = get_settings()

        # Get scheduler config (use defaults if not configured)
        cron_hour = getattr(
            getattr(settings, "scheduler", None), "cron_hour", "0,4,8,12,16,20"
        )
        cron_minute = getattr(getattr(settings, "scheduler", None), "cron_minute", "1")

        self._scheduler = AsyncIOScheduler()

        # Add collection job with cron trigger
        trigger = CronTrigger(hour=cron_hour, minute=cron_minute, timezone="UTC")

        self._scheduler.add_job(
            self._run_collection_job,
            trigger=trigger,
            id="collection_job",
            name="Data Collection",
            replace_existing=True,
        )

        self._scheduler.start()
        self._health_status.is_running = True
        self._health_status.to_file(self._health_file)

        logger.info(
            f"Scheduler started. Collection scheduled at {cron_hour}:{cron_minute} UTC"
        )

    async def stop(self) -> None:
        """Gracefully stop the scheduler."""
        logger.info("Stopping scheduler...")

        if self._scheduler:
            self._scheduler.shutdown(wait=True)
            self._scheduler = None

        self._health_status.is_running = False
        self._health_status.to_file(self._health_file)

        logger.info("Scheduler stopped.")

    async def run_forever(self) -> None:
        """Run scheduler until shutdown signal received."""
        self._setup_signal_handlers()

        await self.start()

        logger.info("Scheduler running. Press Ctrl+C to stop.")

        try:
            await self._shutdown_event.wait()
        finally:
            await self.stop()
