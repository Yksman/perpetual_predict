"""Alert notification functions for Telegram and Discord delivery."""

from pathlib import Path

from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    DiscordWebhook,
    EmbedColors,
)
from perpetual_predict.notifications.telegram_bot import TelegramBot
from perpetual_predict.storage.database import Database
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


async def send_report(
    bot: TelegramBot,
    report_path: str | Path,
) -> bool:
    """Send a report file via Telegram.

    Args:
        bot: TelegramBot instance.
        report_path: Path to the report file.

    Returns:
        True if sent successfully.
    """
    report_path = Path(report_path)

    if not report_path.exists():
        logger.error(f"Report file not found: {report_path}")
        return False

    # Read report content for preview
    content = report_path.read_text()
    preview = content[:500] + "..." if len(content) > 500 else content

    # Send preview message
    await bot.send_message(
        text=f"*New Analysis Report Generated*\n\n{preview}",
        parse_mode="Markdown",
    )

    # Send full report as document
    result = await bot.send_document(
        file_path=report_path,
        caption=f"Full report: {report_path.name}",
    )

    return result is not None


async def check_rsi_extremes(
    database: Database,
    symbol: str = "BTCUSDT",
    overbought_threshold: float = 70.0,
    oversold_threshold: float = 30.0,
) -> dict[str, float | None]:
    """Check for RSI extreme values.

    Args:
        database: Database instance.
        symbol: Trading symbol.
        overbought_threshold: RSI level considered overbought.
        oversold_threshold: RSI level considered oversold.

    Returns:
        Dictionary with RSI value and signal type.
    """
    # Get latest candles for RSI calculation
    candles = await database.get_candles(symbol, "4h", limit=14)

    if len(candles) < 14:
        return {"rsi": None, "signal": None}

    # Calculate RSI (simplified)
    gains = []
    losses = []

    for i in range(1, len(candles)):
        change = candles[i - 1].close - candles[i].close
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    signal = None
    if rsi >= overbought_threshold:
        signal = "overbought"
    elif rsi <= oversold_threshold:
        signal = "oversold"

    return {"rsi": rsi, "signal": signal}


async def send_rsi_alert(
    bot: TelegramBot,
    rsi_value: float,
    signal_type: str,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send RSI extreme alert via Telegram.

    Args:
        bot: TelegramBot instance.
        rsi_value: Current RSI value.
        signal_type: "overbought" or "oversold".
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    if signal_type == "overbought":
        emoji = "🔴"
        message = f"{emoji} *RSI Alert: Overbought*\n\nSymbol: `{symbol}`\nRSI: `{rsi_value:.2f}`\n\nPrice may be due for a correction."
    elif signal_type == "oversold":
        emoji = "🟢"
        message = f"{emoji} *RSI Alert: Oversold*\n\nSymbol: `{symbol}`\nRSI: `{rsi_value:.2f}`\n\nPrice may be due for a bounce."
    else:
        return False

    result = await bot.send_message(text=message, parse_mode="Markdown")
    return result is not None


async def send_sr_alert(
    bot: TelegramBot,
    price: float,
    level: float,
    level_type: str,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send Support/Resistance level alert.

    Args:
        bot: TelegramBot instance.
        price: Current price.
        level: S/R level price.
        level_type: "support" or "resistance".
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    if level_type == "support":
        emoji = "📉"
        message = (
            f"{emoji} *Support Level Alert*\n\n"
            f"Symbol: `{symbol}`\n"
            f"Current Price: `${price:,.2f}`\n"
            f"Support Level: `${level:,.2f}`\n\n"
            "Price is approaching support."
        )
    elif level_type == "resistance":
        emoji = "📈"
        message = (
            f"{emoji} *Resistance Level Alert*\n\n"
            f"Symbol: `{symbol}`\n"
            f"Current Price: `${price:,.2f}`\n"
            f"Resistance Level: `${level:,.2f}`\n\n"
            "Price is approaching resistance."
        )
    else:
        return False

    result = await bot.send_message(text=message, parse_mode="Markdown")
    return result is not None


async def send_status_message(
    bot: TelegramBot,
    database: Database,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send system status message.

    Args:
        bot: TelegramBot instance.
        database: Database instance.
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    # Get latest data counts
    candles = await database.get_candles(symbol, "4h", limit=1)
    funding_rates = await database.get_funding_rates(symbol, limit=1)
    scheduler_runs = await database.get_scheduler_runs(limit=5)

    # Build status message
    lines = [
        "📊 *Perpetual Predict Status*",
        "",
        f"*Symbol:* `{symbol}`",
        "",
        "*Latest Data:*",
    ]

    if candles:
        latest_candle = candles[0]
        lines.append(f"• Price: `${latest_candle.close:,.2f}`")
        lines.append(f"• Last candle: `{latest_candle.close_time.strftime('%Y-%m-%d %H:%M')}`")

    if funding_rates:
        latest_rate = funding_rates[0]
        lines.append(f"• Funding rate: `{latest_rate.funding_rate * 100:.4f}%`")

    lines.append("")
    lines.append("*Recent Jobs:*")

    for run in scheduler_runs[:3]:
        status_emoji = "✅" if run.status == "success" else "❌" if run.status == "failed" else "🔄"
        lines.append(f"• {status_emoji} {run.job_name} ({run.start_time.strftime('%H:%M')})")

    message = "\n".join(lines)
    result = await bot.send_message(text=message, parse_mode="Markdown")
    return result is not None


# Discord Alert Functions


async def send_discord_rsi_alert(
    webhook: DiscordWebhook,
    rsi_value: float,
    signal_type: str,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send RSI extreme alert via Discord.

    Args:
        webhook: DiscordWebhook instance.
        rsi_value: Current RSI value.
        signal_type: "overbought" or "oversold".
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    if signal_type == "overbought":
        color = EmbedColors.BEARISH
        title = "🔴 RSI Alert: Overbought"
        description = "Price may be due for a correction."
    elif signal_type == "oversold":
        color = EmbedColors.BULLISH
        title = "🟢 RSI Alert: Oversold"
        description = "Price may be due for a bounce."
    else:
        return False

    embed = (
        DiscordEmbed(title=title, description=description, color=color)
        .add_field(name="Symbol", value=f"`{symbol}`", inline=True)
        .add_field(name="RSI", value=f"`{rsi_value:.2f}`", inline=True)
        .set_timestamp()
    )

    result = await webhook.send_embed(embed)
    return result is not None


async def send_discord_sr_alert(
    webhook: DiscordWebhook,
    price: float,
    level: float,
    level_type: str,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send Support/Resistance level alert via Discord.

    Args:
        webhook: DiscordWebhook instance.
        price: Current price.
        level: S/R level price.
        level_type: "support" or "resistance".
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    if level_type == "support":
        color = EmbedColors.WARNING
        title = "📉 Support Level Alert"
        description = "Price is approaching support."
    elif level_type == "resistance":
        color = EmbedColors.WARNING
        title = "📈 Resistance Level Alert"
        description = "Price is approaching resistance."
    else:
        return False

    embed = (
        DiscordEmbed(title=title, description=description, color=color)
        .add_field(name="Symbol", value=f"`{symbol}`", inline=True)
        .add_field(name="Current Price", value=f"`${price:,.2f}`", inline=True)
        .add_field(name=level_type.capitalize(), value=f"`${level:,.2f}`", inline=True)
        .set_timestamp()
    )

    result = await webhook.send_embed(embed)
    return result is not None


async def send_discord_status(
    webhook: DiscordWebhook,
    database: Database,
    symbol: str = "BTCUSDT",
) -> bool:
    """Send system status message via Discord.

    Args:
        webhook: DiscordWebhook instance.
        database: Database instance.
        symbol: Trading symbol.

    Returns:
        True if sent successfully.
    """
    # Get latest data
    candles = await database.get_candles(symbol, "4h", limit=1)
    funding_rates = await database.get_funding_rates(symbol, limit=1)
    scheduler_runs = await database.get_scheduler_runs(limit=5)

    embed = DiscordEmbed(
        title="📊 Perpetual Predict Status",
        color=EmbedColors.INFO,
    ).add_field(name="Symbol", value=f"`{symbol}`", inline=False)

    # Add price data
    if candles:
        latest_candle = candles[0]
        embed.add_field(
            name="Price",
            value=f"`${latest_candle.close:,.2f}`",
            inline=True,
        )
        embed.add_field(
            name="Last Candle",
            value=f"`{latest_candle.close_time.strftime('%Y-%m-%d %H:%M')}`",
            inline=True,
        )

    # Add funding rate
    if funding_rates:
        latest_rate = funding_rates[0]
        embed.add_field(
            name="Funding Rate",
            value=f"`{latest_rate.funding_rate * 100:.4f}%`",
            inline=True,
        )

    # Add recent jobs
    if scheduler_runs:
        job_lines = []
        for run in scheduler_runs[:3]:
            status_emoji = (
                "✅" if run.status == "success" else "❌" if run.status == "failed" else "🔄"
            )
            job_lines.append(
                f"{status_emoji} {run.job_name} ({run.start_time.strftime('%H:%M')})"
            )
        embed.add_field(
            name="Recent Jobs",
            value="\n".join(job_lines) or "No recent jobs",
            inline=False,
        )

    embed.set_timestamp()

    result = await webhook.send_embed(embed)
    return result is not None


async def send_discord_report(
    webhook: DiscordWebhook,
    report_path: str | Path,
) -> bool:
    """Send a report file via Discord.

    Args:
        webhook: DiscordWebhook instance.
        report_path: Path to the report file.

    Returns:
        True if sent successfully.
    """
    report_path = Path(report_path)

    if not report_path.exists():
        logger.error(f"Report file not found: {report_path}")
        return False

    # Read report content for preview
    content = report_path.read_text()
    preview = content[:500] + "..." if len(content) > 500 else content

    # Send preview as embed
    embed = DiscordEmbed(
        title="📄 New Analysis Report Generated",
        description=f"```\n{preview}\n```",
        color=EmbedColors.INFO,
    ).set_timestamp()

    await webhook.send_embed(embed)

    # Send full report as file
    result = await webhook.send_file(
        file_path=report_path,
        content=f"Full report: {report_path.name}",
    )

    return result is not None
