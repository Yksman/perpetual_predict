"""Notification services."""

from perpetual_predict.notifications.alerts import (
    check_rsi_extremes,
    send_discord_report,
    send_discord_rsi_alert,
    send_discord_sr_alert,
    send_discord_status,
    send_report,
    send_rsi_alert,
    send_sr_alert,
    send_status_message,
)
from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    DiscordWebhook,
    EmbedColors,
)
from perpetual_predict.notifications.telegram_bot import TelegramBot

__all__ = [
    # Telegram
    "TelegramBot",
    "check_rsi_extremes",
    "send_report",
    "send_rsi_alert",
    "send_sr_alert",
    "send_status_message",
    # Discord
    "DiscordWebhook",
    "DiscordEmbed",
    "EmbedColors",
    "send_discord_rsi_alert",
    "send_discord_sr_alert",
    "send_discord_status",
    "send_discord_report",
]
