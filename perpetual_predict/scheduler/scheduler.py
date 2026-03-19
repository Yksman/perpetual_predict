"""Scheduler manager for automated task execution."""

from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from perpetual_predict.storage.database import Database
from perpetual_predict.storage.models import SchedulerRun
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class SchedulerManager:
    """Manager for APScheduler-based job scheduling.

    Provides job registration, execution tracking, and lifecycle management.
    """

    def __init__(self, database: Database | None = None):
        """Initialize scheduler manager.

        Args:
            database: Database instance for storing run history.
        """
        self._scheduler = AsyncIOScheduler()
        self._database = database
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running and self._scheduler.running

    def add_interval_job(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        job_id: str,
        hours: int | None = None,
        minutes: int | None = None,
        seconds: int | None = None,
        start_date: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        """Add an interval-based job.

        Args:
            func: Async function to execute.
            job_id: Unique job identifier.
            hours: Interval in hours.
            minutes: Interval in minutes.
            seconds: Interval in seconds.
            start_date: When to start the job.
            **kwargs: Additional arguments for the job function.
        """
        trigger = IntervalTrigger(
            hours=hours or 0,
            minutes=minutes or 0,
            seconds=seconds or 0,
            start_date=start_date,
        )

        # Wrap function to track execution
        wrapped_func = self._wrap_job(func, job_id)

        self._scheduler.add_job(
            wrapped_func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )

        logger.info(
            f"Added interval job '{job_id}' with interval: "
            f"{hours or 0}h {minutes or 0}m {seconds or 0}s"
        )

    def _wrap_job(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        job_id: str,
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        """Wrap a job function to track execution.

        Args:
            func: Original async function.
            job_id: Job identifier for logging.

        Returns:
            Wrapped async function.
        """

        async def wrapped(**kwargs: Any) -> None:
            run_id = None
            start_time = datetime.now(timezone.utc)

            # Record job start
            if self._database:
                run = SchedulerRun(
                    job_name=job_id,
                    status="running",
                    start_time=start_time,
                )
                run_id = await self._database.insert_scheduler_run(run)

            logger.info(f"Job '{job_id}' started")

            try:
                await func(**kwargs)
                status = "success"
                logger.info(f"Job '{job_id}' completed successfully")

            except Exception as e:
                status = "failed"
                logger.error(f"Job '{job_id}' failed: {e}")

            finally:
                # Record job completion
                end_time = datetime.now(timezone.utc)
                if self._database and run_id:
                    await self._database.update_scheduler_run(run_id, status, end_time)

        return wrapped

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job.

        Args:
            job_id: Job identifier to remove.

        Returns:
            True if job was removed, False if not found.
        """
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed job '{job_id}'")
            return True
        except Exception:
            logger.warning(f"Job '{job_id}' not found")
            return False

    def get_jobs(self) -> list[dict[str, Any]]:
        """Get list of scheduled jobs.

        Returns:
            List of job information dictionaries.
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._scheduler.start()
        self._running = True
        logger.info("Scheduler started")

    async def stop(self, wait: bool = True) -> None:
        """Stop the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete.
        """
        if not self._running:
            return

        self._scheduler.shutdown(wait=wait)
        self._running = False
        logger.info("Scheduler stopped")

    def pause_job(self, job_id: str) -> None:
        """Pause a scheduled job.

        Args:
            job_id: Job identifier to pause.
        """
        self._scheduler.pause_job(job_id)
        logger.info(f"Paused job '{job_id}'")

    def resume_job(self, job_id: str) -> None:
        """Resume a paused job.

        Args:
            job_id: Job identifier to resume.
        """
        self._scheduler.resume_job(job_id)
        logger.info(f"Resumed job '{job_id}'")

    async def run_job_now(self, job_id: str) -> None:
        """Trigger immediate execution of a job.

        Args:
            job_id: Job identifier to run.
        """
        job = self._scheduler.get_job(job_id)
        if job:
            logger.info(f"Triggering immediate run of job '{job_id}'")
            job.modify(next_run_time=datetime.now(timezone.utc))
        else:
            logger.warning(f"Job '{job_id}' not found")
