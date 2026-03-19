"""Base WebSocket client with reconnection and heartbeat support."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable

import aiohttp

from perpetual_predict.config import get_settings
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class BaseWebSocketClient(ABC):
    """Abstract base class for WebSocket clients with auto-reconnection.

    Features:
    - Automatic reconnection with exponential backoff
    - Ping/pong heartbeat to detect connection issues
    - Callback-based message handling
    """

    def __init__(
        self,
        url: str | None = None,
        reconnect_delay: float | None = None,
        max_reconnect_attempts: int | None = None,
        ping_interval: float | None = None,
        ping_timeout: float | None = None,
    ):
        """Initialize WebSocket client.

        Args:
            url: WebSocket URL. If None, uses settings.
            reconnect_delay: Initial reconnect delay in seconds.
            max_reconnect_attempts: Maximum reconnection attempts.
            ping_interval: Interval between heartbeat pings in seconds.
            ping_timeout: Timeout for ping response in seconds.
        """
        settings = get_settings()
        ws_config = settings.websocket

        self.url = url or ws_config.binance_ws_url
        self.reconnect_delay = reconnect_delay or ws_config.reconnect_delay
        self.max_reconnect_attempts = (
            max_reconnect_attempts or ws_config.max_reconnect_attempts
        )
        self.ping_interval = ping_interval or ws_config.ping_interval
        self.ping_timeout = ping_timeout or ws_config.ping_timeout

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._reconnect_count = 0
        self._ping_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and not self._ws.closed

    def add_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Add a callback for incoming messages.

        Args:
            callback: Function to call with parsed message data.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Remove a callback.

        Args:
            callback: Callback to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @abstractmethod
    def _get_subscribe_message(self) -> dict[str, Any]:
        """Get the subscription message to send after connection.

        Returns:
            Subscription message dictionary.
        """
        pass

    @abstractmethod
    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming message data.

        Args:
            data: Parsed JSON message data.
        """
        pass

    async def connect(self) -> None:
        """Establish WebSocket connection and start listening."""
        if self._running:
            logger.warning("WebSocket client already running")
            return

        self._running = True
        self._reconnect_count = 0

        await self._connect_with_retry()

    async def _connect_with_retry(self) -> None:
        """Connect with automatic retry on failure."""
        while self._running:
            try:
                await self._establish_connection()
                self._reconnect_count = 0  # Reset on successful connection

                # Start background tasks
                self._ping_task = asyncio.create_task(self._ping_loop())
                self._receive_task = asyncio.create_task(self._receive_loop())

                # Wait for receive task to complete (disconnect or error)
                await self._receive_task

            except aiohttp.ClientError as e:
                logger.error(f"WebSocket connection error: {e}")

            except asyncio.CancelledError:
                logger.info("WebSocket client cancelled")
                break

            except Exception as e:
                logger.error(f"Unexpected WebSocket error: {e}")

            finally:
                await self._cleanup_tasks()

            # Handle reconnection
            if self._running:
                self._reconnect_count += 1

                if self._reconnect_count > self.max_reconnect_attempts:
                    logger.error(
                        f"Max reconnection attempts ({self.max_reconnect_attempts}) reached"
                    )
                    self._running = False
                    break

                delay = self.reconnect_delay * (2 ** (self._reconnect_count - 1))
                delay = min(delay, 60.0)  # Cap at 60 seconds
                logger.info(
                    f"Reconnecting in {delay:.1f}s "
                    f"(attempt {self._reconnect_count}/{self.max_reconnect_attempts})"
                )
                await asyncio.sleep(delay)

    async def _establish_connection(self) -> None:
        """Establish the WebSocket connection."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        logger.info(f"Connecting to {self.url}")
        self._ws = await self._session.ws_connect(
            self.url,
            heartbeat=self.ping_interval,
            receive_timeout=self.ping_timeout * 2,
        )
        logger.info("WebSocket connected")

        # Send subscription message
        subscribe_msg = self._get_subscribe_message()
        if subscribe_msg:
            await self._ws.send_json(subscribe_msg)
            logger.debug(f"Sent subscription: {subscribe_msg}")

    async def _ping_loop(self) -> None:
        """Send periodic ping messages."""
        while self._running and self.is_connected:
            try:
                await asyncio.sleep(self.ping_interval)
                if self.is_connected:
                    await self._ws.ping()  # type: ignore
                    logger.debug("Ping sent")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Ping error: {e}")
                break

    async def _receive_loop(self) -> None:
        """Receive and process messages."""
        while self._running and self.is_connected:
            try:
                msg = await self._ws.receive()  # type: ignore

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self._handle_message(data)

                    # Call registered callbacks
                    for callback in self._callbacks:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                elif msg.type == aiohttp.WSMsgType.PONG:
                    logger.debug("Pong received")

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket closed by server")
                    break

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._ws.exception()}")  # type: ignore
                    break

            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                logger.warning("WebSocket receive timeout")
                break
            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                break

    async def _cleanup_tasks(self) -> None:
        """Cancel and cleanup background tasks."""
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None

    async def disconnect(self) -> None:
        """Disconnect and stop the client."""
        logger.info("Disconnecting WebSocket client")
        self._running = False

        await self._cleanup_tasks()

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        logger.info("WebSocket client disconnected")

    async def close(self) -> None:
        """Alias for disconnect."""
        await self.disconnect()
