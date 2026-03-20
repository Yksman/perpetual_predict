"""Scheduler notification functions for Discord delivery."""

from datetime import datetime, timezone

from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    DiscordWebhook,
    EmbedColors,
)
from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.utils import get_logger

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
) -> bool:
    """Send notification when data collection completes successfully.

    Args:
        webhook: DiscordWebhook instance.
        results: Dictionary with counts of collected records.
        duration_seconds: How long the collection took.
        health_status: Optional health status for additional info.
        symbol: Trading symbol.

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
        return result is not None
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
