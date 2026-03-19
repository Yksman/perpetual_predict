"""WebSocket-based collectors."""

from perpetual_predict.collectors.websocket.base import BaseWebSocketClient
from perpetual_predict.collectors.websocket.binance_ws import (
    AggTradeStream,
    AggTradeUpdate,
    CombinedStream,
    MarkPriceStream,
    MarkPriceUpdate,
)

__all__ = [
    "AggTradeStream",
    "AggTradeUpdate",
    "BaseWebSocketClient",
    "CombinedStream",
    "MarkPriceStream",
    "MarkPriceUpdate",
]
