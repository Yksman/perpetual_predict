"""Scheduler job definitions."""

import time
from datetime import datetime, timezone

from perpetual_predict.cli.collect import collect_data
from perpetual_predict.config import get_settings
from perpetual_predict.notifications.discord_webhook import DiscordWebhook
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


async def _get_discord_webhook() -> DiscordWebhook | None:
    """Get Discord webhook if configured and enabled.

    Returns:
        DiscordWebhook instance or None if disabled/unconfigured.
    """
    settings = get_settings()
    if not settings.discord.enabled:
        logger.debug("Discord notifications disabled (DISCORD_ENABLED=false)")
        return None
    if not settings.discord.webhook_url:
        logger.warning(
            "Discord webhook URL not configured. "
            "Set DISCORD_WEBHOOK_URL environment variable to enable notifications."
        )
        return None
    logger.info("Discord notifications enabled")
    return DiscordWebhook()


async def collection_job(health_status: HealthStatus) -> dict[str, int]:
    """Scheduled job to collect all market data.

    Reuses the existing collect_data() function from CLI module.
    Sends Discord notifications on start, complete, or failure.

    Args:
        health_status: Health status tracker to update.

    Returns:
        Dictionary with counts of collected records.
    """
    settings = get_settings()
    job_name = "collection"
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe

    start_time = time.time()
    webhook = await _get_discord_webhook()

    logger.info(
        f"Starting scheduled collection at {datetime.now(timezone.utc).isoformat()}"
    )
    health_status.update_job_started(job_name)

    # Send start notification (don't fail collection if notification fails)
    # Lazy import to avoid circular dependency
    if webhook:
        try:
            from perpetual_predict.notifications.scheduler_alerts import (
                send_collection_started,
            )

            await send_collection_started(webhook, symbol, timeframe)
        except Exception as e:
            logger.warning(f"Failed to send start notification: {e}")

    try:
        results = await collect_data(
            symbol=symbol,
            timeframe=timeframe,
            days=1,  # Only collect recent data for scheduled runs
        )

        duration = time.time() - start_time
        health_status.update_job_completed(job_name, success=True, details=results)
        logger.info(f"Collection completed: {results}")

        # Send completion notification with integrity report
        if webhook:
            try:
                from perpetual_predict.notifications.scheduler_alerts import (
                    send_collection_completed,
                )
                from perpetual_predict.reporters.data_integrity import (
                    verify_data_integrity,
                )
                from perpetual_predict.storage.database import get_database

                # Run data integrity verification
                integrity_report = None
                try:
                    async with get_database() as db:
                        integrity_report = await verify_data_integrity(
                            db, symbol, timeframe, hours=24
                        )
                except Exception as integrity_error:
                    logger.warning(
                        f"Failed to verify data integrity: {integrity_error}"
                    )

                await send_collection_completed(
                    webhook, results, duration, health_status, symbol,
                    integrity_report=integrity_report,
                )
            except Exception as e:
                logger.warning(f"Failed to send completion notification: {e}")

        return results

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        health_status.update_job_completed(job_name, success=False, error=error_msg)
        logger.error(f"Collection failed: {e}")

        # Send failure notification
        if webhook:
            try:
                from perpetual_predict.notifications.scheduler_alerts import (
                    send_collection_failed,
                )

                await send_collection_failed(
                    webhook, error_msg, duration, health_status, symbol
                )
            except Exception as ex:
                logger.warning(f"Failed to send failure notification: {ex}")

        raise
    finally:
        # Clean up webhook session
        if webhook:
            await webhook.close()
