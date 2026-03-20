"""Scheduler job definitions."""

from datetime import datetime, timezone

from perpetual_predict.cli.collect import collect_data
from perpetual_predict.config import get_settings
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


async def collection_job(health_status: HealthStatus) -> dict[str, int]:
    """Scheduled job to collect all market data.

    Reuses the existing collect_data() function from CLI module.

    Args:
        health_status: Health status tracker to update.

    Returns:
        Dictionary with counts of collected records.
    """
    settings = get_settings()
    job_name = "collection"

    logger.info(
        f"Starting scheduled collection at {datetime.now(timezone.utc).isoformat()}"
    )
    health_status.update_job_started(job_name)

    try:
        results = await collect_data(
            symbol=settings.trading.symbol,
            timeframe=settings.trading.timeframe,
            days=1,  # Only collect recent data for scheduled runs
        )

        health_status.update_job_completed(job_name, success=True, details=results)
        logger.info(f"Collection completed: {results}")
        return results

    except Exception as e:
        health_status.update_job_completed(job_name, success=False, error=str(e))
        logger.error(f"Collection failed: {e}")
        raise
