"""Binance Futures WebSocket stream clients."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from perpetual_predict.collectors.websocket.base import BaseWebSocketClient
from perpetual_predict.config import get_settings
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


@dataclass
class MarkPriceUpdate:
    """Mark price update data."""

    symbol: str
    mark_price: float
    index_price: float
    estimated_settle_price: float
    funding_rate: float
    next_funding_time: datetime
    timestamp: datetime


@dataclass
class AggTradeUpdate:
    """Aggregate trade update data."""

    symbol: str
    trade_id: int
    price: float
    quantity: float
    first_trade_id: int
    last_trade_id: int
    timestamp: datetime
    is_buyer_maker: bool


class MarkPriceStream(BaseWebSocketClient):
    """WebSocket client for real-time mark price updates.

    Subscribes to the markPrice@1s stream for the configured symbol.
    """

    def __init__(
        self,
        symbol: str | None = None,
        update_speed: str = "1s",
        **kwargs: Any,
    ):
        """Initialize mark price stream.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT"). If None, uses settings.
            update_speed: Update frequency ("1s" or "3s").
            **kwargs: Additional arguments for BaseWebSocketClient.
        """
        settings = get_settings()
        self.symbol = (symbol or settings.trading.symbol).lower()
        self.update_speed = update_speed

        # Build stream URL
        stream_name = f"{self.symbol}@markPrice@{update_speed}"
        url = f"{settings.websocket.binance_ws_url}/{stream_name}"

        super().__init__(url=url, **kwargs)

        self._latest_update: MarkPriceUpdate | None = None

    @property
    def latest_update(self) -> MarkPriceUpdate | None:
        """Get the latest mark price update."""
        return self._latest_update

    def _get_subscribe_message(self) -> dict[str, Any]:
        """No subscription needed for single stream URL."""
        return {}

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming mark price message.

        Message format:
        {
            "e": "markPriceUpdate",
            "E": 1562305380000,
            "s": "BTCUSDT",
            "p": "11794.15000000",
            "i": "11784.62659091",
            "P": "11784.25641265",
            "r": "0.00038167",
            "T": 1562306400000
        }
        """
        if data.get("e") != "markPriceUpdate":
            return

        self._latest_update = MarkPriceUpdate(
            symbol=data["s"],
            mark_price=float(data["p"]),
            index_price=float(data["i"]),
            estimated_settle_price=float(data["P"]),
            funding_rate=float(data["r"]),
            next_funding_time=datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc),
            timestamp=datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc),
        )

        logger.debug(
            f"Mark price update: {self._latest_update.symbol} "
            f"@ {self._latest_update.mark_price:.2f}"
        )


class AggTradeStream(BaseWebSocketClient):
    """WebSocket client for real-time aggregate trade updates.

    Subscribes to the aggTrade stream for the configured symbol.
    """

    def __init__(
        self,
        symbol: str | None = None,
        **kwargs: Any,
    ):
        """Initialize aggregate trade stream.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT"). If None, uses settings.
            **kwargs: Additional arguments for BaseWebSocketClient.
        """
        settings = get_settings()
        self.symbol = (symbol or settings.trading.symbol).lower()

        # Build stream URL
        stream_name = f"{self.symbol}@aggTrade"
        url = f"{settings.websocket.binance_ws_url}/{stream_name}"

        super().__init__(url=url, **kwargs)

        self._latest_trade: AggTradeUpdate | None = None
        self._trade_count = 0

    @property
    def latest_trade(self) -> AggTradeUpdate | None:
        """Get the latest aggregate trade."""
        return self._latest_trade

    @property
    def trade_count(self) -> int:
        """Get the total number of trades received."""
        return self._trade_count

    def _get_subscribe_message(self) -> dict[str, Any]:
        """No subscription needed for single stream URL."""
        return {}

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming aggregate trade message.

        Message format:
        {
            "e": "aggTrade",
            "E": 1562305380000,
            "a": 26129,
            "s": "BTCUSDT",
            "p": "0.01633102",
            "q": "4.70443515",
            "f": 27781,
            "l": 27781,
            "T": 1562305379040,
            "m": true
        }
        """
        if data.get("e") != "aggTrade":
            return

        self._latest_trade = AggTradeUpdate(
            symbol=data["s"],
            trade_id=data["a"],
            price=float(data["p"]),
            quantity=float(data["q"]),
            first_trade_id=data["f"],
            last_trade_id=data["l"],
            timestamp=datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc),
            is_buyer_maker=data["m"],
        )
        self._trade_count += 1

        logger.debug(
            f"Agg trade: {self._latest_trade.symbol} "
            f"{'SELL' if self._latest_trade.is_buyer_maker else 'BUY'} "
            f"{self._latest_trade.quantity:.4f} @ {self._latest_trade.price:.2f}"
        )


class CombinedStream(BaseWebSocketClient):
    """WebSocket client for multiple combined streams.

    Subscribes to multiple streams in a single connection.
    """

    def __init__(
        self,
        streams: list[str],
        **kwargs: Any,
    ):
        """Initialize combined stream.

        Args:
            streams: List of stream names (e.g., ["btcusdt@markPrice", "btcusdt@aggTrade"]).
            **kwargs: Additional arguments for BaseWebSocketClient.
        """
        settings = get_settings()

        # Build combined stream URL
        stream_param = "/".join(streams)
        url = f"{settings.websocket.binance_ws_url}/stream?streams={stream_param}"

        super().__init__(url=url, **kwargs)

        self.streams = streams
        self._latest_mark_price: MarkPriceUpdate | None = None
        self._latest_trade: AggTradeUpdate | None = None

    @property
    def latest_mark_price(self) -> MarkPriceUpdate | None:
        """Get the latest mark price update."""
        return self._latest_mark_price

    @property
    def latest_trade(self) -> AggTradeUpdate | None:
        """Get the latest aggregate trade."""
        return self._latest_trade

    def _get_subscribe_message(self) -> dict[str, Any]:
        """No subscription needed for stream URL with params."""
        return {}

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming combined stream message.

        Combined stream format:
        {
            "stream": "<streamName>",
            "data": { ... }
        }
        """
        if "stream" not in data or "data" not in data:
            return

        stream_name = data["stream"]
        stream_data = data["data"]

        if "@markPrice" in stream_name:
            self._handle_mark_price(stream_data)
        elif "@aggTrade" in stream_name:
            self._handle_agg_trade(stream_data)

    def _handle_mark_price(self, data: dict[str, Any]) -> None:
        """Handle mark price data from combined stream."""
        self._latest_mark_price = MarkPriceUpdate(
            symbol=data["s"],
            mark_price=float(data["p"]),
            index_price=float(data["i"]),
            estimated_settle_price=float(data["P"]),
            funding_rate=float(data["r"]),
            next_funding_time=datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc),
            timestamp=datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc),
        )

    def _handle_agg_trade(self, data: dict[str, Any]) -> None:
        """Handle aggregate trade data from combined stream."""
        self._latest_trade = AggTradeUpdate(
            symbol=data["s"],
            trade_id=data["a"],
            price=float(data["p"]),
            quantity=float(data["q"]),
            first_trade_id=data["f"],
            last_trade_id=data["l"],
            timestamp=datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc),
            is_buyer_maker=data["m"],
        )
