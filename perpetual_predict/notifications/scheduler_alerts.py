"""Scheduler notification functions for Discord delivery."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    DiscordWebhook,
    EmbedColors,
)
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.utils import get_logger

if TYPE_CHECKING:
    from perpetual_predict.reporters.data_integrity import IntegrityReport
    from perpetual_predict.storage.models import Prediction

logger = get_logger(__name__)


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
            name="⏰ 대상 캔들",
            value=f"`{prediction.target_candle_open.strftime('%Y-%m-%d %H:%M')} UTC`",
            inline=False,
        )
        .add_field(name="📝 주요 판단 요소", value=factors_text, inline=False)
        .set_timestamp()
    )

    # Add reasoning (truncated)
    reasoning = prediction.reasoning
    if len(reasoning) > 500:
        reasoning = reasoning[:497] + "..."
    embed.add_field(name="💭 분석 근거", value=reasoning, inline=False)

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
        embed.set_footer(
            text=f"🤖 Claude Code Headless | {prediction.duration_ms / 1000:.1f}s"
        )

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
