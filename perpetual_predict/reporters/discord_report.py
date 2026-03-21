"""Discord embed generation for data integrity reports."""

from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    EmbedColors,
)
from perpetual_predict.reporters.data_integrity import IntegrityReport


def create_integrity_report_embed(report: IntegrityReport) -> DiscordEmbed:
    """Create Discord embed from IntegrityReport.

    Args:
        report: IntegrityReport containing verification results.

    Returns:
        DiscordEmbed ready for sending.
    """
    # Determine overall color based on health status
    if report.overall_healthy:
        color = EmbedColors.SUCCESS
        title = "📋 데이터 무결성 검증 ✅"
    else:
        color = EmbedColors.WARNING
        title = "📋 데이터 무결성 검증 ⚠️"

    embed = DiscordEmbed(
        title=title,
        description=f"최근 {report.hours_checked}시간 데이터 검증 결과",
        color=color,
    )

    # Candles field
    embed.add_field(
        name="📊 캔들 (4H)",
        value=report.candles.format_status(),
        inline=True,
    )

    # Funding rates field
    embed.add_field(
        name="💰 펀딩비율 (8H)",
        value=report.funding_rates.format_status(),
        inline=True,
    )

    # Add spacing for better layout
    embed.add_field(
        name="\u200b",  # Zero-width space for empty field
        value="\u200b",
        inline=True,
    )

    # Open interest field
    embed.add_field(
        name="📈 미결제약정 (4H)",
        value=report.open_interest.format_status(),
        inline=True,
    )

    # Long/short ratio field
    embed.add_field(
        name="⚖️ 롱/숏 비율 (4H)",
        value=report.long_short_ratio.format_status(),
        inline=True,
    )

    # Fear & Greed field
    embed.add_field(
        name="😱 공포탐욕지수",
        value=report.fear_greed.format_status(),
        inline=True,
    )

    # Set footer with verification time
    embed.footer = (
        f"검증 시간: {report.verification_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    embed.set_timestamp(report.verification_time)

    return embed
