"""Discord Webhook client for sending notifications."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from perpetual_predict.config import get_settings
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class EmbedColors:
    """Discord embed color constants."""

    SUCCESS = 0x00FF00  # Green
    WARNING = 0xFFFF00  # Yellow
    ERROR = 0xFF0000  # Red
    INFO = 0x5865F2  # Discord Blurple
    BULLISH = 0x00FF00  # Green
    BEARISH = 0xFF0000  # Red


@dataclass
class DiscordEmbed:
    """Discord embed message structure.

    Supports rich formatting with title, description, fields, and more.
    """

    title: str = ""
    description: str = ""
    color: int = EmbedColors.INFO
    fields: list[dict[str, Any]] = field(default_factory=list)
    footer: str = ""
    timestamp: str = ""
    thumbnail_url: str = ""
    image_url: str = ""

    def add_field(
        self, name: str, value: str, inline: bool = False
    ) -> "DiscordEmbed":
        """Add a field to the embed.

        Args:
            name: Field name/title.
            value: Field value.
            inline: Whether to display inline with other fields.

        Returns:
            Self for method chaining.
        """
        self.fields.append({"name": name, "value": value, "inline": inline})
        return self

    def set_timestamp(self, dt: datetime | None = None) -> "DiscordEmbed":
        """Set embed timestamp.

        Args:
            dt: Datetime to use. If None, uses current UTC time.

        Returns:
            Self for method chaining.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        self.timestamp = dt.isoformat()
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert embed to Discord API format.

        Returns:
            Dictionary ready for Discord API.
        """
        data: dict[str, Any] = {}

        if self.title:
            data["title"] = self.title
        if self.description:
            data["description"] = self.description[:4096]  # Discord limit
        if self.color:
            data["color"] = self.color
        if self.fields:
            data["fields"] = self.fields[:25]  # Discord limit
        if self.footer:
            data["footer"] = {"text": self.footer[:2048]}  # Discord limit
        if self.timestamp:
            data["timestamp"] = self.timestamp
        if self.thumbnail_url:
            data["thumbnail"] = {"url": self.thumbnail_url}
        if self.image_url:
            data["image"] = {"url": self.image_url}

        return data


class DiscordWebhook:
    """Async Discord Webhook client for message delivery.

    Uses Discord Webhook API directly via aiohttp.
    """

    MAX_CONTENT_LENGTH = 2000
    MAX_EMBEDS = 10

    def __init__(self, webhook_url: str | None = None):
        """Initialize Discord webhook client.

        Args:
            webhook_url: Discord webhook URL. If None, uses settings.
        """
        settings = get_settings()
        discord_config = settings.discord

        self.webhook_url = webhook_url or discord_config.webhook_url
        self.username = discord_config.username
        self.avatar_url = discord_config.avatar_url
        self.enabled = discord_config.enabled

        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @property
    def is_configured(self) -> bool:
        """Check if webhook is properly configured."""
        return bool(self.webhook_url)

    def _build_payload(
        self,
        content: str = "",
        embeds: list[DiscordEmbed] | None = None,
    ) -> dict[str, Any]:
        """Build webhook payload.

        Args:
            content: Text message content.
            embeds: List of embeds to include.

        Returns:
            Payload dictionary for Discord API.
        """
        payload: dict[str, Any] = {}

        if content:
            payload["content"] = content[: self.MAX_CONTENT_LENGTH]

        if self.username:
            payload["username"] = self.username

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        if embeds:
            payload["embeds"] = [
                e.to_dict() for e in embeds[: self.MAX_EMBEDS]
            ]

        return payload

    async def send_message(self, content: str) -> dict[str, Any] | None:
        """Send a text message.

        Args:
            content: Message text (max 2000 characters).

        Returns:
            API response or None on failure.
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled, skipping message")
            return None

        if not self.is_configured:
            logger.warning("Discord webhook not configured")
            return None

        payload = self._build_payload(content=content)

        try:
            async with self.session.post(
                self.webhook_url,
                json=payload,
                params={"wait": "true"},
            ) as response:
                if response.status == 204:
                    logger.debug("Message sent (no content response)")
                    return {"ok": True}

                if response.status == 200:
                    data = await response.json()
                    logger.debug("Message sent successfully")
                    return data

                # Handle errors
                error_text = await response.text()
                logger.error(
                    f"Discord API error: {response.status} - {error_text}"
                )
                return None

        except aiohttp.ClientError as e:
            logger.error(f"Discord request failed: {e}")
            return None

    async def send_embed(
        self,
        embed: DiscordEmbed,
        content: str = "",
    ) -> dict[str, Any] | None:
        """Send a rich embed message.

        Args:
            embed: DiscordEmbed object.
            content: Optional text message alongside embed.

        Returns:
            API response or None on failure.
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled, skipping embed")
            return None

        if not self.is_configured:
            logger.warning("Discord webhook not configured")
            return None

        payload = self._build_payload(content=content, embeds=[embed])

        try:
            async with self.session.post(
                self.webhook_url,
                json=payload,
                params={"wait": "true"},
            ) as response:
                if response.status in (200, 204):
                    logger.debug("Embed sent successfully")
                    if response.status == 200:
                        return await response.json()
                    return {"ok": True}

                error_text = await response.text()
                logger.error(
                    f"Discord API error: {response.status} - {error_text}"
                )
                return None

        except aiohttp.ClientError as e:
            logger.error(f"Discord request failed: {e}")
            return None

    async def send_file(
        self,
        file_path: str | Path,
        content: str = "",
    ) -> dict[str, Any] | None:
        """Send a file attachment.

        Args:
            file_path: Path to file to send.
            content: Optional text message with file.

        Returns:
            API response or None on failure.
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled, skipping file")
            return None

        if not self.is_configured:
            logger.warning("Discord webhook not configured")
            return None

        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            # Build multipart form data
            data = aiohttp.FormData()

            # Add JSON payload
            payload = self._build_payload(content=content)
            data.add_field(
                "payload_json",
                json.dumps(payload),
                content_type="application/json",
            )

            # Add file
            data.add_field(
                "file",
                open(file_path, "rb"),
                filename=file_path.name,
            )

            async with self.session.post(
                self.webhook_url,
                data=data,
                params={"wait": "true"},
            ) as response:
                if response.status in (200, 204):
                    logger.debug(f"File sent: {file_path.name}")
                    if response.status == 200:
                        return await response.json()
                    return {"ok": True}

                error_text = await response.text()
                logger.error(
                    f"Discord API error: {response.status} - {error_text}"
                )
                return None

        except aiohttp.ClientError as e:
            logger.error(f"Discord request failed: {e}")
            return None

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
