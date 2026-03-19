"""Liquidation data collector for Binance Futures API."""

from datetime import datetime, timezone
from typing import Any

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import Liquidation
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class LiquidationCollector(BaseCollector):
    """Collector for liquidation (force order) data."""

    def __init__(
        self,
        client: BinanceClient | None = None,
        symbol: str | None = None,
    ):
        """Initialize liquidation collector.

        Args:
            client: BinanceClient instance. If None, creates a new one.
            symbol: Trading pair symbol. If None, uses settings.
        """
        self.client = client or BinanceClient()
        self._owns_client = client is None

        settings = get_settings()
        self.symbol = symbol or settings.trading.symbol

    async def collect(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> list[Liquidation]:
        """Collect liquidation data.

        Args:
            start_time: Start time for data collection.
            end_time: End time for data collection.
            limit: Maximum number of records to collect.
            **kwargs: Additional arguments (ignored).

        Returns:
            List of Liquidation objects.
        """
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None

        logger.info(f"Collecting liquidations for {self.symbol}, limit={limit}")

        raw_data = await self.client.get_force_orders(
            symbol=self.symbol,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )

        liquidations = [self._parse_liquidation(data) for data in raw_data]
        logger.info(f"Collected {len(liquidations)} liquidation records")

        return liquidations

    def _parse_liquidation(self, data: dict[str, Any]) -> Liquidation:
        """Parse raw liquidation data into Liquidation object.

        Data format from Binance:
        {
            "symbol": "BTCUSDT",
            "price": "7918.33",
            "origQty": "0.014",
            "executedQty": "0.014",
            "averagePrice": "7918.33",
            "status": "FILLED",
            "timeInForce": "IOC",
            "type": "LIMIT",
            "side": "SELL",
            "time": 1568014460893
        }
        """
        return Liquidation(
            symbol=data["symbol"],
            side=data["side"],
            price=float(data["price"]),
            original_qty=float(data["origQty"]),
            timestamp=datetime.fromtimestamp(data["time"] / 1000, tz=timezone.utc),
        )

    async def close(self) -> None:
        """Close the client if owned."""
        if self._owns_client:
            await self.client.close()
