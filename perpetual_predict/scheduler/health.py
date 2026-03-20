"""Health check and status management for scheduler."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JobStatus:
    """Status of a scheduled job."""

    last_run: str | None = None
    last_success: str | None = None
    last_error: str | None = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class HealthStatus:
    """Overall scheduler health status."""

    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_running: bool = False
    jobs: dict[str, JobStatus] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "started_at": self.started_at,
            "is_running": self.is_running,
            "jobs": {name: asdict(status) for name, status in self.jobs.items()},
        }

    def to_file(self, path: Path) -> None:
        """Write status to JSON file for external monitoring.

        Args:
            path: Path to write the status file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.debug(f"Health status written to {path}")

    @classmethod
    def from_file(cls, path: Path) -> "HealthStatus":
        """Load status from JSON file.

        Args:
            path: Path to the status file.

        Returns:
            HealthStatus instance.
        """
        if not path.exists():
            return cls()

        with open(path) as f:
            data = json.load(f)

        status = cls(
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            is_running=data.get("is_running", False),
        )

        for name, job_data in data.get("jobs", {}).items():
            status.jobs[name] = JobStatus(**job_data)

        return status

    def update_job_started(self, job_name: str) -> None:
        """Update status when a job starts.

        Args:
            job_name: Name of the job.
        """
        if job_name not in self.jobs:
            self.jobs[job_name] = JobStatus()

        self.jobs[job_name].last_run = datetime.now(timezone.utc).isoformat()
        self.jobs[job_name].run_count += 1

    def update_job_completed(
        self,
        job_name: str,
        success: bool,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update status when a job completes.

        Args:
            job_name: Name of the job.
            success: Whether the job succeeded.
            error: Error message if failed.
            details: Additional details about the job result.
        """
        if job_name not in self.jobs:
            self.jobs[job_name] = JobStatus()

        if success:
            self.jobs[job_name].last_success = datetime.now(timezone.utc).isoformat()
            self.jobs[job_name].success_count += 1
            self.jobs[job_name].last_error = None
            logger.info(f"Job '{job_name}' completed successfully: {details}")
        else:
            self.jobs[job_name].failure_count += 1
            self.jobs[job_name].last_error = error
            logger.error(f"Job '{job_name}' failed: {error}")
