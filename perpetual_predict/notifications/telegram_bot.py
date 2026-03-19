"""Telegram Bot client for sending notifications."""

from pathlib import Path
from typing import Any

import aiohttp

from perpetual_predict.config import get_settings
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class TelegramBot:
    """Async Telegram Bot client for message and file delivery.

    Uses Telegram Bot API directly via aiohttp.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ):
        """Initialize Telegram bot client.

        Args:
            bot_token: Telegram bot token. If None, uses settings.
            chat_id: Target chat ID. If None, uses settings.
        """
        settings = get_settings()
        tg_config = settings.telegram

        self.bot_token = bot_token or tg_config.bot_token
        self.chat_id = chat_id or tg_config.chat_id
        self.api_url = tg_config.api_url
        self.enabled = tg_config.enabled

        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @property
    def is_configured(self) -> bool:
        """Check if bot is properly configured."""
        return bool(self.bot_token and self.chat_id)

    def _get_api_url(self, method: str) -> str:
        """Get full API URL for a method.

        Args:
            method: Telegram API method name.

        Returns:
            Full API URL.
        """
        return f"{self.api_url}/bot{self.bot_token}/{method}"

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "Markdown",
        disable_notification: bool = False,
    ) -> dict[str, Any] | None:
        """Send a text message.

        Args:
            text: Message text (max 4096 characters).
            chat_id: Target chat ID. If None, uses default.
            parse_mode: Text formatting mode ("Markdown", "HTML", or None).
            disable_notification: Send silently.

        Returns:
            API response or None on failure.
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled, skipping message")
            return None

        if not self.is_configured:
            logger.warning("Telegram bot not configured")
            return None

        target_chat = chat_id or self.chat_id

        # Split long messages
        if len(text) > 4096:
            logger.warning("Message too long, truncating to 4096 characters")
            text = text[:4093] + "..."

        payload = {
            "chat_id": target_chat,
            "text": text,
            "disable_notification": disable_notification,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            url = self._get_api_url("sendMessage")
            async with self.session.post(url, json=payload) as response:
                data = await response.json()

                if not data.get("ok"):
                    error = data.get("description", "Unknown error")
                    logger.error(f"Telegram API error: {error}")
                    return None

                logger.debug(f"Message sent to {target_chat}")
                return data

        except aiohttp.ClientError as e:
            logger.error(f"Telegram request failed: {e}")
            return None

    async def send_document(
        self,
        file_path: str | Path,
        chat_id: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a document file.

        Args:
            file_path: Path to file to send.
            chat_id: Target chat ID. If None, uses default.
            caption: Optional file caption.

        Returns:
            API response or None on failure.
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled, skipping document")
            return None

        if not self.is_configured:
            logger.warning("Telegram bot not configured")
            return None

        target_chat = chat_id or self.chat_id
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            url = self._get_api_url("sendDocument")

            data = aiohttp.FormData()
            data.add_field("chat_id", target_chat)
            data.add_field(
                "document",
                open(file_path, "rb"),
                filename=file_path.name,
            )
            if caption:
                data.add_field("caption", caption[:1024])  # Max caption length

            async with self.session.post(url, data=data) as response:
                result = await response.json()

                if not result.get("ok"):
                    error = result.get("description", "Unknown error")
                    logger.error(f"Telegram API error: {error}")
                    return None

                logger.debug(f"Document sent to {target_chat}")
                return result

        except aiohttp.ClientError as e:
            logger.error(f"Telegram request failed: {e}")
            return None

    async def get_me(self) -> dict[str, Any] | None:
        """Get bot information.

        Returns:
            Bot info or None on failure.
        """
        if not self.bot_token:
            return None

        try:
            url = self._get_api_url("getMe")
            async with self.session.get(url) as response:
                data = await response.json()
                return data.get("result") if data.get("ok") else None

        except aiohttp.ClientError as e:
            logger.error(f"Telegram request failed: {e}")
            return None

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
