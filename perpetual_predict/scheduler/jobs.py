"""Scheduler job definitions."""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone

from perpetual_predict.cli.collect import collect_data
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.notifications.discord_webhook import DiscordWebhook
from perpetual_predict.reporters.data_integrity import (
    LatestDataVerification,
    verify_latest_data,
)
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.storage.database import get_database
from perpetual_predict.storage.models import Prediction
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class DataIntegrityError(Exception):
    """데이터 검증 실패 시 발생하는 예외."""

    def __init__(self, message: str, verification: LatestDataVerification | None = None):
        super().__init__(message)
        self.verification = verification

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


async def collect_with_verification(
    health_status: HealthStatus,
    symbol: str,
    timeframe: str,
    max_retries: int = 5,
    retry_delays: list[float] | None = None,
    send_notifications: bool = True,
) -> tuple[dict[str, int], LatestDataVerification]:
    """데이터 수집 후 최신 데이터 검증을 수행.

    수집 후 모든 데이터 타입(Candle, Funding, OI, LS)이
    최신 타임스탬프를 가지고 있는지 검증합니다.
    검증 실패 시 빠른 재시도를 수행합니다.

    Args:
        health_status: 헬스 상태 추적기
        symbol: 거래 심볼
        timeframe: 타임프레임
        max_retries: 최대 재시도 횟수 (기본: 5)
        retry_delays: 재시도 대기 시간 목록 (기본: [2, 4, 6, 8, 10])
        send_notifications: 디스코드 알림 전송 여부

    Returns:
        tuple: (수집 결과 dict, 검증 결과)

    Raises:
        DataIntegrityError: 모든 재시도 실패 시
    """
    if retry_delays is None:
        retry_delays = [2.0, 4.0, 6.0, 8.0, 10.0]

    webhook = await _get_discord_webhook() if send_notifications else None

    last_results: dict[str, int] = {}
    last_verification: LatestDataVerification | None = None

    for attempt in range(max_retries):
        try:
            # 재시도 대기 (첫 시도 제외)
            if attempt > 0:
                delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                logger.info(f"Retry {attempt}/{max_retries}: waiting {delay:.0f}s...")

                await asyncio.sleep(delay)

            # 데이터 수집
            logger.info(f"Collection attempt {attempt + 1}/{max_retries}")
            last_results = await collection_job(health_status)

            # 최신 데이터 검증
            async with get_database() as db:
                last_verification = await verify_latest_data(
                    db=db,
                    symbol=symbol,
                    timeframe=timeframe,
                    tolerance_minutes=5,
                )

            if last_verification.all_verified:
                logger.info(
                    f"Data verification PASSED on attempt {attempt + 1} - "
                    f"all {last_verification.verified_count} data types verified"
                )

                # 검증 성공 알림
                if webhook:
                    try:
                        from perpetual_predict.notifications.scheduler_alerts import (
                            send_verification_report,
                        )
                        await send_verification_report(webhook, last_verification, symbol)
                    except Exception as e:
                        logger.warning(f"Failed to send verification report: {e}")

                return last_results, last_verification
            else:
                logger.warning(
                    f"Data verification FAILED on attempt {attempt + 1}: "
                    f"missing {last_verification.missing_data} "
                    f"({last_verification.verified_count}/{last_verification.total_types})"
                )

        except Exception as e:
            logger.error(f"Collection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise

    # 모든 재시도 소진
    error_msg = (
        f"Data verification failed after {max_retries} attempts. "
        f"Missing: {last_verification.missing_data if last_verification else 'unknown'}"
    )
    logger.error(error_msg)

    raise DataIntegrityError(error_msg, last_verification)


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

        health_status.update_job_completed(job_name, success=True, details=results)
        logger.info(f"Collection completed: {results}")

        return results

    except Exception as e:
        error_msg = str(e)
        health_status.update_job_completed(job_name, success=False, error=error_msg)
        logger.error(f"Collection failed: {e}")
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

    # The target candle is the CURRENT candle (just started after previous close)
    target_candle_open = current_candle_open
    target_candle_close = current_candle_open + timedelta(hours=hours_per_candle)

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


async def _fetch_sub_candles_1h(
    symbol: str,
    timeframe: str,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> list[list] | None:
    """Fetch 1H candles covering the previous 4H window from Binance API.

    Used to provide sub-timeframe breakdown of the just-closed 4H candle,
    giving the prediction agent insight into the "shape of the move."

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Base timeframe (e.g., "4h") to determine the window.
        max_retries: Maximum fetch attempts before fallback.
        retry_delay: Seconds to wait between retries.

    Returns:
        List of 4 raw Binance kline arrays, or None on failure.
    """
    settings = get_settings()

    # Calculate the previous 4H candle window
    now = datetime.now(timezone.utc)
    hours_per_candle = 4 if timeframe.lower() == "4h" else 1
    current_candle_hour = (now.hour // hours_per_candle) * hours_per_candle
    current_candle_open = now.replace(
        hour=current_candle_hour, minute=0, second=0, microsecond=0
    )
    # Previous 4H candle: from (current_open - 4h) to current_open
    prev_candle_open = current_candle_open - timedelta(hours=hours_per_candle)

    start_ms = int(prev_candle_open.timestamp() * 1000)
    end_ms = int(current_candle_open.timestamp() * 1000) - 1  # exclusive

    for attempt in range(max_retries):
        client = BinanceClient(
            api_key=settings.binance.api_key,
            api_secret=settings.binance.api_secret,
            use_testnet=settings.binance.use_testnet,
        )
        try:
            klines = await client.get_klines(
                symbol=symbol,
                interval="1h",
                start_time=start_ms,
                end_time=end_ms,
                limit=4,
            )
            if klines and len(klines) >= 4:
                logger.info(
                    f"Fetched {len(klines)} 1H sub-candles for "
                    f"{prev_candle_open.strftime('%H:%M')}-"
                    f"{current_candle_open.strftime('%H:%M')} UTC"
                )
                return klines[:4]
            else:
                logger.warning(
                    f"1H sub-candle fetch returned {len(klines) if klines else 0} "
                    f"candles (expected 4), attempt {attempt + 1}/{max_retries}"
                )
        except Exception as e:
            logger.warning(
                f"1H sub-candle fetch failed (attempt {attempt + 1}/{max_retries}): {e}"
            )
        finally:
            await client.close()

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    logger.warning("1H sub-candle fetch failed after all retries, proceeding without")
    return None


async def _run_single_prediction(
    market_context,
    target_open: datetime,
    target_close: datetime,
    symbol: str,
    timeframe: str,
    enabled_modules: list[str] | None = None,
    experiment_id: str | None = None,
    arm: str = "baseline",
    account_id: str = "default",
) -> Prediction | None:
    """Run a single prediction with the given module configuration.

    This is the core prediction logic extracted for reuse across
    baseline and experiment arms.
    """
    from perpetual_predict.llm.agent.runner import run_prediction_agent

    settings = get_settings()

    # Format context with specific modules
    prompt = market_context.format_prompt(enabled_modules=enabled_modules)
    log_prefix = f"[{arm}]" if experiment_id else ""
    logger.debug(f"{log_prefix} Market context prompt:\n{prompt[:500]}...")

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
        position_pct=agent_result.position_pct,
        trading_reasoning=agent_result.trading_reasoning,
        bull_case=agent_result.bull_case,
        bear_case=agent_result.bear_case,
    )

    # Save to database + open paper trade
    async with get_database() as db:
        await db.insert_prediction(prediction, experiment_id=experiment_id, arm=arm)

        # Paper trading: open position
        paper_settings = settings.paper_trading
        if (
            paper_settings.enabled
            and prediction.direction != "NEUTRAL"
            and prediction.position_pct > 0
        ):
            try:
                from perpetual_predict.trading.engine import PaperTradingEngine
                engine = PaperTradingEngine(db, account_id)
                await engine.ensure_account(paper_settings.initial_balance)
                candles = await db.get_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=target_open,
                    end_time=target_open,
                    limit=1,
                )
                if candles:
                    trade = await engine.open_position(prediction, candles[0].open)
                    if trade:
                        logger.info(
                            f"{log_prefix} Paper trade opened: {trade.side} "
                            f"position_pct={trade.position_pct:.2f}x "
                            f"notional=${trade.notional_value:.2f}"
                        )
                else:
                    logger.warning(
                        f"{log_prefix} No candle data for entry price, "
                        "paper trade skipped"
                    )
            except Exception as e:
                logger.warning(f"{log_prefix} Paper trading open failed (non-fatal): {e}")

    logger.info(
        f"{log_prefix} Prediction generated: {prediction.direction} "
        f"(confidence: {prediction.confidence:.0%}, "
        f"position_pct: {prediction.position_pct:.2f}x) "
        f"for candle {target_open.isoformat()}"
    )

    return prediction


async def prediction_job(
    health_status: HealthStatus,
) -> tuple[Prediction | None, list[tuple]]:
    """Scheduled job to generate LLM prediction for current candle.

    Builds market context from collected data and runs Claude Code
    headless agent to predict the direction of the current candle (just started).

    Also runs experiment arm predictions if any active experiments exist
    and EXPERIMENT_ENABLED=true.

    Args:
        health_status: Health status tracker to update.

    Returns:
        Tuple of (baseline_prediction, variant_results).
        variant_results is a list of (experiment, variant_prediction) tuples.
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
        from perpetual_predict.llm.context.builder import MarketContextBuilder

        # Calculate target candle times
        target_open, target_close = _calculate_target_candle_times(timeframe)

        # Fetch 1H sub-candles for previous 4H window (live from Binance)
        sub_candles_1h = await _fetch_sub_candles_1h(symbol, timeframe)

        # Build market context (shared across all arms — same market data)
        paper_settings = settings.paper_trading
        async with get_database() as db:
            context_builder = MarketContextBuilder(db, symbol, timeframe)
            market_context = await context_builder.build(
                sub_candles_1h=sub_candles_1h,
            )

        # 1. Baseline prediction (always runs, same as before)
        prediction = await _run_single_prediction(
            market_context=market_context,
            target_open=target_open,
            target_close=target_close,
            symbol=symbol,
            timeframe=timeframe,
            enabled_modules=None,  # all modules
            experiment_id=None,
            arm="baseline",
            account_id=paper_settings.account_id,
        )

        # 2. Experiment arm predictions (parallel, max 4 concurrent)
        variant_results: list[tuple] = []

        if settings.experiment.enabled:
            async with get_database() as db:
                active_experiments = await db.get_active_experiments()

            # Build prediction tasks for all variants across all experiments
            variant_tasks = []

            for exp in active_experiments:
                # Reuse baseline as control arm
                if prediction:
                    try:
                        async with get_database() as db:
                            control_pred = Prediction(
                                prediction_id=str(uuid.uuid4()),
                                prediction_time=prediction.prediction_time,
                                target_candle_open=target_open,
                                target_candle_close=target_close,
                                symbol=symbol,
                                timeframe=timeframe,
                                direction=prediction.direction,
                                confidence=prediction.confidence,
                                reasoning=prediction.reasoning,
                                key_factors=prediction.key_factors,
                                session_id=prediction.session_id,
                                duration_ms=prediction.duration_ms,
                                model_usage=prediction.model_usage,
                                position_pct=prediction.position_pct,
                                trading_reasoning=prediction.trading_reasoning,
                            )
                            await db.insert_prediction(
                                control_pred,
                                experiment_id=exp.experiment_id,
                                arm="control",
                            )

                            # Open paper trade for control arm
                            if (
                                paper_settings.enabled
                                and control_pred.direction != "NEUTRAL"
                                and control_pred.position_pct > 0
                            ):
                                from perpetual_predict.trading.engine import PaperTradingEngine
                                ctrl_account_id = f"{exp.experiment_id}_control"
                                engine = PaperTradingEngine(db, ctrl_account_id)
                                await engine.ensure_account(paper_settings.initial_balance)
                                candles = await db.get_candles(
                                    symbol=symbol, timeframe=timeframe,
                                    start_time=target_open, end_time=target_open, limit=1,
                                )
                                if candles:
                                    trade = await engine.open_position(control_pred, candles[0].open)
                                    if trade:
                                        logger.info(
                                            f"[control] Paper trade opened (reused baseline): "
                                            f"{trade.side} notional=${trade.notional_value:.2f}"
                                        )
                        logger.info(
                            f"[control] Reused baseline prediction for {exp.experiment_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Experiment {exp.experiment_id} control "
                            f"(baseline reuse) failed (non-fatal): {e}"
                        )

                # Queue variant prediction tasks
                for variant_name, modules in exp.variants.items():
                    variant_tasks.append((
                        exp,
                        variant_name,
                        _run_single_prediction(
                            market_context=market_context,
                            target_open=target_open,
                            target_close=target_close,
                            symbol=symbol,
                            timeframe=timeframe,
                            enabled_modules=modules,
                            experiment_id=exp.experiment_id,
                            arm=f"variant_{variant_name}",
                            account_id=f"{exp.experiment_id}_variant_{variant_name}",
                        ),
                    ))

            # Execute variant predictions in parallel (max 4 at a time)
            MAX_CONCURRENT = 4
            for batch_start in range(0, len(variant_tasks), MAX_CONCURRENT):
                batch = variant_tasks[batch_start:batch_start + MAX_CONCURRENT]
                batch_coros = [task[2] for task in batch]
                batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)

                for i, result in enumerate(batch_results):
                    exp_item, vname, _ = batch[i]
                    if isinstance(result, Exception):
                        logger.warning(
                            f"Experiment {exp_item.experiment_id} variant_{vname} "
                            f"prediction failed (non-fatal): {result}"
                        )
                    elif result:
                        variant_results.append((exp_item, vname, result))

        health_status.update_job_completed(
            job_name,
            success=True,
            details={
                "direction": prediction.direction if prediction else "N/A",
                "confidence": prediction.confidence if prediction else 0,
                "target_candle": target_open.isoformat(),
                "position_pct": prediction.position_pct if prediction else 0,
            },
        )

        return prediction, variant_results

    except Exception as e:
        error_msg = str(e)
        health_status.update_job_completed(job_name, success=False, error=error_msg)
        logger.error(f"Prediction failed: {e}")
        raise


async def full_cycle_job(health_status: HealthStatus) -> dict:
    """Full prediction cycle: collect → evaluate → predict → notify.

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

    # Wait for latest candle to close before proceeding (reduced wait time)
    logger.info("Phase 0: Verifying latest candle is closed in API...")
    candle_ready = await _wait_for_candle_close(
        symbol=symbol,
        timeframe=timeframe,
        max_wait_seconds=30,  # Reduced from 120s - verification handles retries
        check_interval=5,    # Reduced from 10s for faster detection
    )
    if not candle_ready:
        logger.warning("Candle not confirmed closed in API, proceeding to collection")

    results = {
        "evaluation": None,
        "collection": None,
        "verification": None,
        "prediction": None,
        "success": False,
    }

    try:
        # Phase 1: Collect new market data + Verify latest data
        # NOTE: Collection runs FIRST to ensure evaluation uses fresh candle data
        logger.info("Phase 1/3: Collecting market data with verification...")
        collection_results, verification = await collect_with_verification(
            health_status=health_status,
            symbol=symbol,
            timeframe=timeframe,
            max_retries=5,
            retry_delays=[2.0, 4.0, 6.0, 8.0, 10.0],
            send_notifications=True,
        )
        results["collection"] = collection_results
        results["verification"] = {
            "all_verified": verification.all_verified,
            "verified_count": verification.verified_count,
            "missing_data": verification.missing_data,
            "candle_time": (
                verification.latest_candle.open_time.isoformat()
                if verification.latest_candle else None
            ),
        }

        # Phase 2: Evaluate previous predictions (with fresh candle data)
        logger.info("Phase 2/3: Evaluating previous predictions...")
        try:
            evaluation_results = await evaluation_job(health_status)
            results["evaluation"] = {
                "count": len(evaluation_results),
                "results": evaluation_results,
            }
        except Exception as e:
            logger.warning(f"Evaluation phase failed (non-fatal): {e}")
            results["evaluation"] = {"error": str(e)}

        # Phase 3: Generate prediction
        logger.info("Phase 3/3: Generating prediction...")
        prediction, variant_results = await prediction_job(health_status)
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
                "data_verified": True,
                "verified_count": verification.verified_count,
            },
        )

        # Send Discord notification with full cycle results
        if webhook and prediction:
            try:
                from perpetual_predict.notifications.scheduler_alerts import (
                    send_news_digest,
                    send_no_experiment,
                    send_prediction_completed,
                    send_variant_prediction,
                )

                # Base prediction message
                await send_prediction_completed(
                    webhook,
                    prediction,
                    results.get("evaluation", {}),
                    health_status,
                )

                # News digest (separate message after prediction)
                await send_news_digest(webhook)

                # Variant predictions as separate messages
                if variant_results:
                    for exp, vname, variant_pred in variant_results:
                        await send_variant_prediction(webhook, variant_pred, exp, vname)
                else:
                    await send_no_experiment(webhook)
            except Exception as e:
                logger.warning(f"Failed to send prediction notification: {e}")

        # Dashboard export (if enabled)
        if get_settings().dashboard.export_enabled:
            try:
                from perpetual_predict.export.exporter import (
                    export_dashboard_data,
                    push_to_data_branch,
                )

                export_path = await export_dashboard_data()
                logger.info(f"Dashboard data exported to {export_path}")

                if get_settings().dashboard.auto_push:
                    push_to_data_branch(export_path)
            except Exception as e:
                logger.warning(f"Dashboard export failed (non-fatal): {e}")

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
