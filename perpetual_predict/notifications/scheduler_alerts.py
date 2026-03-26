"""Scheduler notification functions for Discord delivery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    DiscordWebhook,
    EmbedColors,
)
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.utils import get_logger

if TYPE_CHECKING:
    from perpetual_predict.experiment.models import Experiment
    from perpetual_predict.reporters.data_integrity import (
        IntegrityReport,
        LatestDataVerification,
    )
    from perpetual_predict.storage.models import Prediction

logger = get_logger(__name__)

# KST timezone offset (UTC+9)
KST_OFFSET = timedelta(hours=9)


async def send_collection_started(
    webhook: DiscordWebhook,
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
) -> bool:
    """Send notification when data collection starts.

    Args:
        webhook: DiscordWebhook instance.
        symbol: Trading symbol.
        timeframe: Candle timeframe.

    Returns:
        True if sent successfully.
    """
    embed = (
        DiscordEmbed(
            title="🚀 데이터 수집 시작",
            description="예약된 데이터 수집이 시작되었습니다.",
            color=EmbedColors.INFO,
        )
        .add_field(name="심볼", value=f"`{symbol}`", inline=True)
        .add_field(name="타임프레임", value=f"`{timeframe}`", inline=True)
        .add_field(
            name="시작 시간",
            value=f"`{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC`",
            inline=False,
        )
        .set_timestamp()
    )

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send collection started notification: {e}")
        return False


async def send_collection_completed(
    webhook: DiscordWebhook,
    results: dict[str, int],
    duration_seconds: float,
    health_status: HealthStatus | None = None,
    symbol: str = "BTCUSDT",
    integrity_report: IntegrityReport | None = None,
) -> bool:
    """Send notification when data collection completes successfully.

    Args:
        webhook: DiscordWebhook instance.
        results: Dictionary with counts of collected records.
        duration_seconds: How long the collection took.
        health_status: Optional health status for additional info.
        symbol: Trading symbol.
        integrity_report: Optional data integrity verification report.

    Returns:
        True if sent successfully.
    """
    total = sum(results.values())

    # Build results summary
    results_lines = [
        f"• 캔들: `{results.get('candles', 0)}`개",
        f"• 펀딩 비율: `{results.get('funding_rates', 0)}`개",
        f"• 미결제약정: `{results.get('open_interests', 0)}`개",
        f"• 롱/숏 비율: `{results.get('long_short_ratios', 0)}`개",
        f"• 공포탐욕지수: `{results.get('fear_greed', 0)}`개",
        f"• 매크로지표: `{results.get('macro_indicators', 0)}`개",
    ]

    embed = (
        DiscordEmbed(
            title="✅ 데이터 수집 완료",
            description="예약된 데이터 수집이 성공적으로 완료되었습니다.",
            color=EmbedColors.SUCCESS,
        )
        .add_field(name="심볼", value=f"`{symbol}`", inline=True)
        .add_field(name="총 레코드", value=f"`{total}`개", inline=True)
        .add_field(
            name="소요 시간",
            value=f"`{duration_seconds:.1f}`초",
            inline=True,
        )
        .add_field(
            name="📊 수집 결과",
            value="\n".join(results_lines),
            inline=False,
        )
        .set_timestamp()
    )

    # Add health status info if available
    if health_status:
        job_status = health_status.jobs.get("collection")
        if job_status:
            embed.add_field(
                name="📈 작업 통계",
                value=(
                    f"• 성공: `{job_status.success_count}`회\n"
                    f"• 실패: `{job_status.failure_count}`회"
                ),
                inline=True,
            )

    try:
        result = await webhook.send_embed(embed)
        success = result is not None

        # Send integrity report embed if available
        if success and integrity_report:
            from perpetual_predict.reporters.discord_report import (
                create_integrity_report_embed,
            )

            integrity_embed = create_integrity_report_embed(integrity_report)
            await webhook.send_embed(integrity_embed)

        return success
    except Exception as e:
        logger.error(f"Failed to send collection completed notification: {e}")
        return False


async def send_collection_failed(
    webhook: DiscordWebhook,
    error: str,
    duration_seconds: float,
    health_status: HealthStatus | None = None,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send notification when data collection fails.

    Args:
        webhook: DiscordWebhook instance.
        error: Error message.
        duration_seconds: How long before failure.
        health_status: Optional health status for additional info.
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    # Truncate long errors
    truncated_error = error[:1000] if len(error) > 1000 else error

    embed = (
        DiscordEmbed(
            title="❌ 데이터 수집 실패",
            description="예약된 데이터 수집 중 오류가 발생했습니다.",
            color=EmbedColors.ERROR,
        )
        .add_field(name="심볼", value=f"`{symbol}`", inline=True)
        .add_field(
            name="소요 시간",
            value=f"`{duration_seconds:.1f}`초",
            inline=True,
        )
        .add_field(
            name="🔴 오류 내용",
            value=f"```\n{truncated_error}\n```",
            inline=False,
        )
        .set_timestamp()
    )

    # Add failure count if available
    if health_status:
        job_status = health_status.jobs.get("collection")
        if job_status:
            embed.add_field(
                name="📊 실패 통계",
                value=f"• 연속 실패: `{job_status.failure_count}`회",
                inline=True,
            )

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send collection failed notification: {e}")
        return False


def _get_direction_emoji(direction: str) -> str:
    """Get emoji for prediction direction."""
    return {"UP": "⬆️", "DOWN": "⬇️", "NEUTRAL": "➡️"}.get(direction.upper(), "❓")


def _format_confidence(confidence: float) -> str:
    """Format confidence as percentage with color indicator."""
    pct = confidence * 100
    if confidence >= 0.7:
        return f"🟢 `{pct:.0f}%`"
    elif confidence >= 0.5:
        return f"🟡 `{pct:.0f}%`"
    else:
        return f"🔴 `{pct:.0f}%`"


async def send_prediction_completed(
    webhook: DiscordWebhook,
    prediction: Prediction,
    evaluation_results: dict[str, Any] | None = None,
    health_status: HealthStatus | None = None,
) -> bool:
    """Send notification when prediction cycle completes successfully.

    Args:
        webhook: DiscordWebhook instance.
        prediction: The prediction object.
        evaluation_results: Optional results from evaluating previous predictions.
        health_status: Optional health status for additional info.

    Returns:
        True if sent successfully.
    """
    direction_emoji = _get_direction_emoji(prediction.direction)
    confidence_display = _format_confidence(prediction.confidence)

    # Format key factors
    factors_text = "\n".join(f"• {factor}" for factor in prediction.key_factors[:5])
    if not factors_text:
        factors_text = "없음"

    embed = (
        DiscordEmbed(
            title="🔮 LLM 예측 완료",
            description=f"다음 {prediction.timeframe} 캔들 방향 예측이 완료되었습니다.",
            color=EmbedColors.SUCCESS,
        )
        .add_field(name="심볼", value=f"`{prediction.symbol}`", inline=True)
        .add_field(
            name="예측 방향",
            value=f"{direction_emoji} **{prediction.direction}**",
            inline=True,
        )
        .add_field(name="신뢰도", value=confidence_display, inline=True)
        .add_field(
            name="⏰ 캔들 종료",
            value=f"`{_format_datetime_kst(prediction.target_candle_close)}`",
            inline=False,
        )
        .add_field(
            name="💰 트레이딩 파라미터",
            value=(
                f"• 레버리지: `{prediction.leverage:.1f}x`\n"
                f"• 투입 비중: `{prediction.position_ratio:.0%}`"
            ),
            inline=True,
        )
        .add_field(name="📝 주요 판단 요소", value=factors_text, inline=False)
        .set_timestamp()
    )

    # Add reasoning (truncated)
    reasoning = prediction.reasoning
    if len(reasoning) > 500:
        reasoning = reasoning[:497] + "..."
    embed.add_field(name="💭 분석 근거", value=reasoning, inline=False)

    # Add full trading reasoning
    if prediction.trading_reasoning:
        trading_reasoning = prediction.trading_reasoning
        if len(trading_reasoning) > 1024:
            trading_reasoning = trading_reasoning[:1021] + "..."
        embed.add_field(
            name="📈 트레이딩 판단 근거",
            value=trading_reasoning,
            inline=False,
        )

    # Add previous prediction evaluation summary if available
    if evaluation_results and evaluation_results.get("results"):
        eval_list = evaluation_results["results"]
        total = len(eval_list)
        correct = sum(1 for r in eval_list if r.get("is_correct"))

        # Most recent evaluation
        latest = eval_list[-1] if eval_list else None
        if latest:
            latest_emoji = "✅" if latest.get("is_correct") else "❌"
            latest_dir = latest.get("predicted_direction", "?")
            latest_actual = latest.get("actual_direction", "?")
            latest_change = latest.get("actual_price_change", 0)

            embed.add_field(
                name="📊 이전 예측 평가",
                value=(
                    f"{latest_emoji} 예측: {_get_direction_emoji(latest_dir)} → "
                    f"실제: {_get_direction_emoji(latest_actual)} ({latest_change:+.2f}%)\n"
                    f"평가된 예측: `{correct}/{total}` 정확"
                ),
                inline=False,
            )

    # Add Claude Code metadata
    if prediction.duration_ms > 0:
        embed.footer = f"🤖 Claude Code Headless | {prediction.duration_ms / 1000:.1f}s"

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send prediction completed notification: {e}")
        return False


async def send_cycle_failed(
    webhook: DiscordWebhook,
    error: str,
    duration_seconds: float,
    health_status: HealthStatus | None = None,
) -> bool:
    """Send notification when full prediction cycle fails.

    Args:
        webhook: DiscordWebhook instance.
        error: Error message.
        duration_seconds: How long before failure.
        health_status: Optional health status for additional info.

    Returns:
        True if sent successfully.
    """
    # Truncate long errors
    truncated_error = error[:1000] if len(error) > 1000 else error

    embed = (
        DiscordEmbed(
            title="❌ 예측 사이클 실패",
            description="예약된 예측 사이클 중 오류가 발생했습니다.",
            color=EmbedColors.ERROR,
        )
        .add_field(
            name="소요 시간",
            value=f"`{duration_seconds:.1f}`초",
            inline=True,
        )
        .add_field(
            name="🔴 오류 내용",
            value=f"```\n{truncated_error}\n```",
            inline=False,
        )
        .set_timestamp()
    )

    # Add failure count if available
    if health_status:
        job_status = health_status.jobs.get("full_cycle")
        if job_status:
            embed.add_field(
                name="📊 실패 통계",
                value=f"• 연속 실패: `{job_status.failure_count}`회",
                inline=True,
            )

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send cycle failed notification: {e}")
        return False


def _format_datetime_short(dt: datetime | None) -> str:
    """Format datetime in short format (UTC)."""
    if dt is None:
        return "N/A"
    return dt.strftime("%m-%d %H:%M")


def _format_datetime_kst(dt: datetime | None) -> str:
    """Format datetime in KST timezone."""
    if dt is None:
        return "N/A"
    kst_time = dt + KST_OFFSET
    return kst_time.strftime("%Y-%m-%d %H:%M KST")


async def send_verification_report(
    webhook: DiscordWebhook,
    verification: LatestDataVerification,
    symbol: str = "BTCUSDT",
) -> bool:
    """검증 결과와 각 데이터 타입별 최신 레코드를 전송.

    Args:
        webhook: DiscordWebhook 인스턴스
        verification: 데이터 검증 결과
        symbol: 거래 심볼

    Returns:
        True if sent successfully
    """
    if verification.all_verified:
        color = EmbedColors.SUCCESS
        title = "📊 데이터 검증 완료"
        description = "모든 데이터가 최신 상태로 확인되었습니다."
    else:
        color = EmbedColors.WARNING
        title = f"📊 데이터 검증 ({verification.verified_count}/{verification.total_types})"
        description = f"일부 데이터 미수집: {', '.join(verification.missing_data)}"

    embed = (
        DiscordEmbed(
            title=title,
            description=description,
            color=color,
        )
        .add_field(name="심볼", value=f"`{symbol}`", inline=True)
        .add_field(
            name="검증 시간",
            value=f"`{verification.verified_at.strftime('%H:%M:%S')} UTC`",
            inline=True,
        )
        .set_timestamp()
    )

    # 4H Candle
    candle_status = "✅" if verification.candle_4h else "❌"
    if verification.latest_candle:
        c = verification.latest_candle
        candle_text = (
            f"{candle_status} **4H Candle**\n"
            f"open_time: `{_format_datetime_short(c.open_time)} UTC`\n"
            f"close: `${c.close:,.2f}`\n"
            f"volume: `{c.volume:,.2f} BTC`"
        )
    else:
        candle_text = (
            f"{candle_status} **4H Candle**\n"
            f"기대: `{_format_datetime_short(verification.expected_candle_time)} UTC`\n"
            f"❌ 데이터 없음"
        )
    embed.add_field(name="", value=candle_text, inline=True)

    # 8H Funding Rate
    funding_status = "✅" if verification.funding_rate_8h else "❌"
    if verification.latest_funding:
        f = verification.latest_funding
        funding_text = (
            f"{funding_status} **8H Funding**\n"
            f"funding_time: `{_format_datetime_short(f.funding_time)} UTC`\n"
            f"rate: `{f.funding_rate * 100:.4f}%`\n"
            f"mark: `${f.mark_price:,.2f}`"
        )
    else:
        funding_text = (
            f"{funding_status} **8H Funding**\n"
            f"기대: `{_format_datetime_short(verification.expected_funding_time)} UTC`\n"
            f"❌ 데이터 없음"
        )
    embed.add_field(name="", value=funding_text, inline=True)

    # 4H Open Interest
    oi_status = "✅" if verification.open_interest_4h else "❌"
    if verification.latest_oi:
        o = verification.latest_oi
        oi_text = (
            f"{oi_status} **4H OI**\n"
            f"timestamp: `{_format_datetime_short(o.timestamp)} UTC`\n"
            f"OI: `{o.open_interest:,.2f} BTC`"
        )
    else:
        oi_text = (
            f"{oi_status} **4H OI**\n"
            f"기대: `{_format_datetime_short(verification.expected_oi_time)} UTC`\n"
            f"❌ 데이터 없음"
        )
    embed.add_field(name="", value=oi_text, inline=True)

    # 4H Long/Short Ratio
    ls_status = "✅" if verification.long_short_ratio_4h else "❌"
    if verification.latest_ls:
        ls = verification.latest_ls
        ls_text = (
            f"{ls_status} **4H LS Ratio**\n"
            f"timestamp: `{_format_datetime_short(ls.timestamp)} UTC`\n"
            f"ratio: `{ls.long_short_ratio:.3f}` (L:{ls.long_ratio*100:.1f}%)"
        )
    else:
        ls_text = (
            f"{ls_status} **4H LS Ratio**\n"
            f"기대: `{_format_datetime_short(verification.expected_ls_time)} UTC`\n"
            f"❌ 데이터 없음"
        )
    embed.add_field(name="", value=ls_text, inline=True)

    # Macro (Daily)
    macro_status = "✅" if verification.macro_daily else "⚠️"
    if verification.macro_indicator_count > 0:
        macro_text = (
            f"{macro_status} **Macro (Daily)**\n"
            f"indicators: `{verification.macro_indicator_count}`개\n"
            f"latest: `{verification.macro_latest_date}`"
        )
    else:
        macro_text = (
            f"{macro_status} **Macro (Daily)**\n"
            f"❌ 데이터 없음"
        )
    embed.add_field(name="", value=macro_text, inline=True)

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send verification report: {e}")
        return False


async def send_verification_retry(
    webhook: DiscordWebhook,
    verification: LatestDataVerification,
    attempt: int,
    max_attempts: int,
    delay_seconds: float,
    symbol: str = "BTCUSDT",
) -> bool:
    """검증 실패 시 재시도 알림 전송.

    Args:
        webhook: DiscordWebhook 인스턴스
        verification: 데이터 검증 결과
        attempt: 현재 시도 횟수
        max_attempts: 최대 시도 횟수
        delay_seconds: 다음 재시도까지 대기 시간
        symbol: 거래 심볼

    Returns:
        True if sent successfully
    """
    embed = (
        DiscordEmbed(
            title=f"🔄 데이터 재수집 중 ({attempt}/{max_attempts})",
            description=f"미수집 데이터: {', '.join(verification.missing_data)}",
            color=EmbedColors.WARNING,
        )
        .add_field(name="심볼", value=f"`{symbol}`", inline=True)
        .add_field(
            name="다음 시도",
            value=f"`{delay_seconds:.0f}초` 후",
            inline=True,
        )
        .set_timestamp()
    )

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send verification retry notification: {e}")
        return False


async def send_verification_failed(
    webhook: DiscordWebhook,
    verification: LatestDataVerification,
    attempts: int,
    symbol: str = "BTCUSDT",
) -> bool:
    """데이터 검증 최종 실패 알림 전송.

    Args:
        webhook: DiscordWebhook 인스턴스
        verification: 데이터 검증 결과
        attempts: 총 시도 횟수
        symbol: 거래 심볼

    Returns:
        True if sent successfully
    """
    # 각 데이터별 상세 상태
    status_lines = []

    # Candle
    if verification.candle_4h:
        status_lines.append(f"✅ 4H Candle: `{_format_datetime_short(verification.latest_candle.open_time if verification.latest_candle else None)} UTC`")
    else:
        expected = _format_datetime_short(verification.expected_candle_time)
        actual = _format_datetime_short(verification.latest_candle.open_time if verification.latest_candle else None)
        status_lines.append(f"❌ 4H Candle: 기대 `{expected}` / 실제 `{actual}`")

    # Funding
    if verification.funding_rate_8h:
        status_lines.append(f"✅ 8H Funding: `{_format_datetime_short(verification.latest_funding.funding_time if verification.latest_funding else None)} UTC`")
    else:
        expected = _format_datetime_short(verification.expected_funding_time)
        actual = _format_datetime_short(verification.latest_funding.funding_time if verification.latest_funding else None)
        status_lines.append(f"❌ 8H Funding: 기대 `{expected}` / 실제 `{actual}`")

    # OI
    if verification.open_interest_4h:
        status_lines.append(f"✅ 4H OI: `{_format_datetime_short(verification.latest_oi.timestamp if verification.latest_oi else None)} UTC`")
    else:
        expected = _format_datetime_short(verification.expected_oi_time)
        actual = _format_datetime_short(verification.latest_oi.timestamp if verification.latest_oi else None)
        status_lines.append(f"❌ 4H OI: 기대 `{expected}` / 실제 `{actual}`")

    # LS Ratio
    if verification.long_short_ratio_4h:
        status_lines.append(f"✅ 4H LS: `{_format_datetime_short(verification.latest_ls.timestamp if verification.latest_ls else None)} UTC`")
    else:
        expected = _format_datetime_short(verification.expected_ls_time)
        actual = _format_datetime_short(verification.latest_ls.timestamp if verification.latest_ls else None)
        status_lines.append(f"❌ 4H LS: 기대 `{expected}` / 실제 `{actual}`")

    embed = (
        DiscordEmbed(
            title="🚫 데이터 검증 실패",
            description="최신 데이터 검증에 실패하여 예측 사이클이 중단되었습니다.",
            color=EmbedColors.ERROR,
        )
        .add_field(name="심볼", value=f"`{symbol}`", inline=True)
        .add_field(name="시도 횟수", value=f"`{attempts}`회", inline=True)
        .add_field(
            name="📊 데이터 상태",
            value="\n".join(status_lines),
            inline=False,
        )
        .add_field(
            name="원인 분석",
            value=(
                "• Binance API 지연\n"
                "• 네트워크 연결 문제\n"
                "• 거래소 데이터 지연"
            ),
            inline=False,
        )
        .set_timestamp()
    )

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send verification failed notification: {e}")
        return False


async def send_variant_prediction(
    webhook: DiscordWebhook,
    prediction: Prediction,
    experiment: Experiment,
) -> bool:
    """Send variant experiment prediction as a separate Discord message.

    Args:
        webhook: DiscordWebhook instance.
        prediction: The variant prediction object.
        experiment: The experiment this variant belongs to.

    Returns:
        True if sent successfully.
    """
    import json

    direction_emoji = _get_direction_emoji(prediction.direction)
    confidence_display = _format_confidence(prediction.confidence)

    # Parse variant modules for display
    variant_modules = experiment.variant_modules
    if isinstance(variant_modules, str):
        variant_modules = json.loads(variant_modules)
    added_modules = set(variant_modules) - set(
        experiment.control_modules
        if isinstance(experiment.control_modules, list)
        else json.loads(experiment.control_modules)
    )
    modules_display = ", ".join(f"`{m}`" for m in sorted(added_modules)) or "없음"

    factors_text = "\n".join(f"• {factor}" for factor in prediction.key_factors[:5])
    if not factors_text:
        factors_text = "없음"

    embed = (
        DiscordEmbed(
            title=f"🧪 Variant 예측 — {experiment.name}",
            description=f"실험 `{experiment.experiment_id}` variant arm 예측 결과",
            color=EmbedColors.INFO,
        )
        .add_field(
            name="추가 모듈",
            value=modules_display,
            inline=True,
        )
        .add_field(
            name="예측 방향",
            value=f"{direction_emoji} **{prediction.direction}**",
            inline=True,
        )
        .add_field(name="신뢰도", value=confidence_display, inline=True)
        .add_field(
            name="💰 트레이딩 파라미터",
            value=(
                f"• 레버리지: `{prediction.leverage:.1f}x`\n"
                f"• 투입 비중: `{prediction.position_ratio:.0%}`"
            ),
            inline=True,
        )
        .add_field(name="📝 주요 판단 요소", value=factors_text, inline=False)
    )

    # Reasoning
    reasoning = prediction.reasoning
    if len(reasoning) > 500:
        reasoning = reasoning[:497] + "..."
    embed.add_field(name="💭 분석 근거", value=reasoning, inline=False)

    # Trading reasoning
    if prediction.trading_reasoning:
        trading_reasoning = prediction.trading_reasoning
        if len(trading_reasoning) > 1024:
            trading_reasoning = trading_reasoning[:1021] + "..."
        embed.add_field(
            name="📈 트레이딩 판단 근거",
            value=trading_reasoning,
            inline=False,
        )

    embed.set_timestamp()

    if prediction.duration_ms > 0:
        embed.footer = f"🤖 Claude Code Headless | {prediction.duration_ms / 1000:.1f}s"

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send variant prediction notification: {e}")
        return False


async def send_no_experiment(
    webhook: DiscordWebhook,
) -> bool:
    """Send notification indicating no active experiments.

    Args:
        webhook: DiscordWebhook instance.

    Returns:
        True if sent successfully.
    """
    embed = (
        DiscordEmbed(
            title="🧪 실험 없음",
            description="현재 활성화된 A/B 실험이 없습니다.",
            color=0x808080,  # gray
        )
        .set_timestamp()
    )

    try:
        result = await webhook.send_embed(embed)
        return result is not None
    except Exception as e:
        logger.error(f"Failed to send no experiment notification: {e}")
        return False
