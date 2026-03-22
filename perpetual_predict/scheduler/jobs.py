"""Scheduler job definitions."""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone

from perpetual_predict.cli.collect import collect_data
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.notifications.discord_webhook import DiscordWebhook
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.storage.database import get_database
from perpetual_predict.storage.models import Prediction
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

# Timeframe to milliseconds mapping
TIMEFRAME_MS = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


async def _wait_for_candle_close(
    symbol: str,
    timeframe: str,
    max_wait_seconds: int = 120,
    check_interval: int = 10,
) -> bool:
    """Wait until the latest candle is fully closed.

    Binance kline data includes close_time which is the end of the candle.
    This function verifies the most recent candle's close_time is in the past.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Candle timeframe (e.g., "4h").
        max_wait_seconds: Maximum time to wait (default 120s).
        check_interval: Seconds between checks (default 10s).

    Returns:
        True if candle is closed, False if timeout reached.
    """
    settings = get_settings()
    client = BinanceClient(
        api_key=settings.binance.api_key,
        api_secret=settings.binance.api_secret,
        use_testnet=settings.binance.use_testnet,
    )

    try:
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            # Fetch the latest 2 klines
            klines = await client.get_klines(symbol, timeframe, limit=2)

            if not klines or len(klines) < 2:
                logger.warning("Could not fetch klines, retrying...")
                await asyncio.sleep(check_interval)
                continue

            # Kline format: [open_time, open, high, low, close, volume, close_time, ...]
            # The second-to-last kline should be fully closed
            latest_closed_kline = klines[-2]
            close_time_ms = int(latest_closed_kline[6])
            close_time = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc)

            now = datetime.now(timezone.utc)

            if close_time < now:
                logger.info(
                    f"Candle closed at {close_time.isoformat()}, "
                    f"current time: {now.isoformat()}"
                )
                return True

            wait_remaining = (close_time - now).total_seconds()
            logger.info(
                f"Waiting for candle to close... "
                f"(closes in {wait_remaining:.0f}s)"
            )
            await asyncio.sleep(min(check_interval, wait_remaining + 1))

        logger.warning(f"Timeout waiting for candle close after {max_wait_seconds}s")
        return False

    finally:
        await client.close()


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


def _calculate_target_candle_times(
    timeframe: str,
) -> tuple[datetime, datetime]:
    """Calculate the target candle open and close times for prediction.

    For 4H timeframe, candles open at 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC.

    Args:
        timeframe: Trading timeframe (e.g., "4h").

    Returns:
        Tuple of (target_candle_open, target_candle_close).
    """
    now = datetime.now(timezone.utc)

    if timeframe.lower() == "4h":
        hours_per_candle = 4
    elif timeframe.lower() == "1h":
        hours_per_candle = 1
    else:
        # Default to 4H
        hours_per_candle = 4

    # Find the current candle's open time
    current_hour = now.hour
    candle_start_hour = (current_hour // hours_per_candle) * hours_per_candle
    current_candle_open = now.replace(
        hour=candle_start_hour, minute=0, second=0, microsecond=0
    )

    # The target candle is the NEXT candle
    target_candle_open = current_candle_open + timedelta(hours=hours_per_candle)
    target_candle_close = target_candle_open + timedelta(hours=hours_per_candle)

    return target_candle_open, target_candle_close


async def evaluation_job(health_status: HealthStatus) -> list[dict]:
    """Scheduled job to evaluate pending predictions.

    Checks all predictions whose target candles have closed and
    compares predicted vs actual direction.

    Args:
        health_status: Health status tracker to update.

    Returns:
        List of evaluation results.
    """
    job_name = "evaluation"
    settings = get_settings()
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe

    logger.info(
        f"Starting prediction evaluation at {datetime.now(timezone.utc).isoformat()}"
    )
    health_status.update_job_started(job_name)

    try:
        from perpetual_predict.llm.evaluation.evaluator import PredictionEvaluator

        async with get_database() as db:
            evaluator = PredictionEvaluator(db, symbol, timeframe)
            results = await evaluator.evaluate_pending_predictions()

        health_status.update_job_completed(
            job_name,
            success=True,
            details={"evaluated_count": len(results)},
        )
        logger.info(f"Evaluation completed: {len(results)} predictions evaluated")

        return results

    except Exception as e:
        error_msg = str(e)
        health_status.update_job_completed(job_name, success=False, error=error_msg)
        logger.error(f"Evaluation failed: {e}")
        raise


async def prediction_job(health_status: HealthStatus) -> Prediction | None:
    """Scheduled job to generate LLM prediction for next candle.

    Builds market context from collected data and runs Claude Code
    headless agent to predict the direction of the next candle.

    Args:
        health_status: Health status tracker to update.

    Returns:
        Prediction object or None if prediction failed.
    """
    job_name = "prediction"
    settings = get_settings()
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe

    logger.info(
        f"Starting prediction generation at {datetime.now(timezone.utc).isoformat()}"
    )
    health_status.update_job_started(job_name)

    try:
        from perpetual_predict.llm.agent.runner import run_prediction_agent
        from perpetual_predict.llm.context.builder import MarketContextBuilder

        # Calculate target candle times
        target_open, target_close = _calculate_target_candle_times(timeframe)

        # Build market context
        async with get_database() as db:
            context_builder = MarketContextBuilder(db, symbol, timeframe)
            market_context = await context_builder.build()

        # Format context as prompt
        prompt = market_context.format_prompt()
        logger.debug(f"Market context prompt:\n{prompt[:500]}...")

        # Run Claude Code prediction agent
        agent_result = await run_prediction_agent(prompt)

        # Create prediction record
        prediction = Prediction(
            prediction_id=str(uuid.uuid4()),
            prediction_time=datetime.now(timezone.utc),
            target_candle_open=target_open,
            target_candle_close=target_close,
            symbol=symbol,
            timeframe=timeframe,
            direction=agent_result.direction,
            confidence=agent_result.confidence,
            reasoning=agent_result.reasoning,
            key_factors=agent_result.key_factors,
            session_id=agent_result.session_id,
            duration_ms=agent_result.duration_ms,
            model_usage=agent_result.model_usage,
        )

        # Save to database
        async with get_database() as db:
            await db.insert_prediction(prediction)

        health_status.update_job_completed(
            job_name,
            success=True,
            details={
                "direction": prediction.direction,
                "confidence": prediction.confidence,
                "target_candle": target_open.isoformat(),
            },
        )
        logger.info(
            f"Prediction generated: {prediction.direction} "
            f"(confidence: {prediction.confidence:.0%}) "
            f"for candle {target_open.isoformat()}"
        )

        return prediction

    except Exception as e:
        error_msg = str(e)
        health_status.update_job_completed(job_name, success=False, error=error_msg)
        logger.error(f"Prediction failed: {e}")
        raise


async def full_cycle_job(health_status: HealthStatus) -> dict:
    """Full prediction cycle: evaluate → collect → predict → notify.

    This is the main scheduled job that orchestrates the entire
    prediction workflow every 4H.

    Args:
        health_status: Health status tracker to update.

    Returns:
        Dictionary with results from all phases.
    """
    job_name = "full_cycle"

    start_time = time.time()
    webhook = await _get_discord_webhook()

    logger.info(
        f"Starting full prediction cycle at {datetime.now(timezone.utc).isoformat()}"
    )
    health_status.update_job_started(job_name)

    settings = get_settings()
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe

    # Wait for latest candle to close before proceeding
    logger.info("Verifying latest candle is closed...")
    candle_ready = await _wait_for_candle_close(
        symbol=symbol,
        timeframe=timeframe,
        max_wait_seconds=120,
        check_interval=10,
    )
    if not candle_ready:
        logger.warning("Proceeding despite candle close timeout")

    results = {
        "evaluation": None,
        "collection": None,
        "prediction": None,
        "success": False,
    }

    try:
        # Phase 1: Evaluate previous predictions
        logger.info("Phase 1/3: Evaluating previous predictions...")
        try:
            evaluation_results = await evaluation_job(health_status)
            results["evaluation"] = {
                "count": len(evaluation_results),
                "results": evaluation_results,
            }
        except Exception as e:
            logger.warning(f"Evaluation phase failed (non-fatal): {e}")
            results["evaluation"] = {"error": str(e)}

        # Phase 2: Collect new market data
        logger.info("Phase 2/3: Collecting market data...")
        collection_results = await collection_job(health_status)
        results["collection"] = collection_results

        # Phase 3: Generate prediction
        logger.info("Phase 3/3: Generating prediction...")
        prediction = await prediction_job(health_status)
        if prediction:
            results["prediction"] = {
                "id": prediction.prediction_id,
                "direction": prediction.direction,
                "confidence": prediction.confidence,
                "target_candle": prediction.target_candle_open.isoformat(),
                "reasoning": prediction.reasoning,
                "key_factors": prediction.key_factors,
            }

        results["success"] = True
        duration = time.time() - start_time

        health_status.update_job_completed(
            job_name,
            success=True,
            details={
                "duration_seconds": duration,
                "phases_completed": 3,
            },
        )

        # Send Discord notification with full cycle results
        if webhook and prediction:
            try:
                from perpetual_predict.notifications.scheduler_alerts import (
                    send_prediction_completed,
                )

                await send_prediction_completed(
                    webhook,
                    prediction,
                    results.get("evaluation", {}),
                    health_status,
                )
            except Exception as e:
                logger.warning(f"Failed to send prediction notification: {e}")

        logger.info(f"Full cycle completed in {duration:.1f}s")
        return results

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        results["error"] = error_msg
        health_status.update_job_completed(job_name, success=False, error=error_msg)
        logger.error(f"Full cycle failed: {e}")

        # Send failure notification
        if webhook:
            try:
                from perpetual_predict.notifications.scheduler_alerts import (
                    send_cycle_failed,
                )

                await send_cycle_failed(webhook, error_msg, duration, health_status)
            except Exception as ex:
                logger.warning(f"Failed to send failure notification: {ex}")

        raise

    finally:
        if webhook:
            await webhook.close()


async def full_cycle_with_retry(
    health_status: HealthStatus,
    max_retries: int = 3,
    retry_delays: list[int] | None = None,
) -> dict:
    """Full prediction cycle with automatic retry on failure.

    Wraps full_cycle_job with exponential backoff retry logic.
    Useful when transient failures (network, API) may resolve on retry.

    Args:
        health_status: Health status tracker to update.
        max_retries: Maximum number of retry attempts (default 3).
        retry_delays: List of delays in seconds between retries.
                      Defaults to [60, 120, 180] (1, 2, 3 minutes).

    Returns:
        Dictionary with results from successful cycle.

    Raises:
        Exception: If all retries are exhausted.
    """
    if retry_delays is None:
        retry_delays = [60, 120, 180]  # 1, 2, 3 minutes

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}...")

            return await full_cycle_job(health_status)

        except Exception as e:
            last_error = e
            logger.error(f"Cycle attempt {attempt + 1} failed: {e}")

            if attempt < max_retries:
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                logger.info(f"Waiting {delay}s before retry...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed")

    # Should not reach here, but raise last error if it does
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected retry loop exit")
