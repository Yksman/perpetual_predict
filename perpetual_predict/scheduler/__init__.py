"""Scheduler module for automated tasks."""

from perpetual_predict.scheduler.jobs import (
    collection_job,
    report_job,
    setup_all_jobs,
    setup_collection_job,
    setup_report_job,
)
from perpetual_predict.scheduler.scheduler import SchedulerManager

__all__ = [
    "SchedulerManager",
    "collection_job",
    "report_job",
    "setup_all_jobs",
    "setup_collection_job",
    "setup_report_job",
]
