"""Liquidation (force orders) collector for Binance Futures API."""

from datetime import datetime, timedelta, timezone
from typing import Any

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import Liquidation
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class LiquidationCollector(BaseCollector):
    """Collector for liquidation (force order) data.

    Aggregates individual liquidation orders into time periods (e.g., 4H).
    """

    def __init__(
        self,
        client: BinanceClient | None = None,
        symbol: str | None = None,
    ):
        """Initialize Liquidation collector.

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
        limit: int = 1000,
        **kwargs: Any,
    ) -> list[Liquidation]:
        """Collect and aggregate liquidation data for a time period.

        Args:
            start_time: Start of aggregation period. If None, uses last 4H.
            end_time: End of aggregation period. If None, uses now.
            limit: Maximum number of raw liquidation records (max 1000).
            **kwargs: Additional arguments (ignored).

        Returns:
            List of Liquidation objects (usually 1 for the period).
        """
        now = datetime.now(timezone.utc)

        if end_time is None:
            end_time = now
        if start_time is None:
            start_time = end_time - timedelta(hours=4)

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        logger.info(
            f"Collecting liquidations for {self.symbol} "
            f"from {start_time.isoformat()} to {end_time.isoformat()}"
        )

        try:
            raw_data = await self.client.get_force_orders(
                symbol=self.symbol,
                start_time=start_ms,
                end_time=end_ms,
                limit=limit,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch liquidation data: {e}")
            # Return empty liquidation on error (API may not be available)
            return [
                Liquidation(
                    symbol=self.symbol,
                    timestamp=end_time,
                    long_liquidation_volume=0.0,
                    short_liquidation_volume=0.0,
                    total_liquidation_volume=0.0,
                    liquidation_count=0,
                )
            ]

        # Aggregate liquidations
        liquidation = self._aggregate_liquidations(raw_data, end_time)
        logger.info(
            f"Collected {liquidation.liquidation_count} liquidations: "
            f"Long={liquidation.long_liquidation_volume:.4f} BTC, "
            f"Short={liquidation.short_liquidation_volume:.4f} BTC"
        )

        return [liquidation]

    def _aggregate_liquidations(
        self,
        raw_data: list[dict[str, Any]],
        timestamp: datetime,
    ) -> Liquidation:
        """Aggregate raw liquidation orders into summary.

        Binance force order format:
        {
            "symbol": "BTCUSDT",
            "price": "65000.00",
            "origQty": "0.001",
            "executedQty": "0.001",
            "averagePrice": "65000.00",
            "status": "FILLED",
            "timeInForce": "IOC",
            "type": "LIMIT",
            "side": "SELL",  # SELL = long liquidated, BUY = short liquidated
            "time": 1234567890000
        }
        """
        long_liq_volume = 0.0
        short_liq_volume = 0.0

        for order in raw_data:
            qty = float(order.get("executedQty", 0))
            side = order.get("side", "")

            # SELL side = long position being liquidated
            # BUY side = short position being liquidated
            if side == "SELL":
                long_liq_volume += qty
            elif side == "BUY":
                short_liq_volume += qty

        total_volume = long_liq_volume + short_liq_volume

        return Liquidation(
            symbol=self.symbol,
            timestamp=timestamp,
            long_liquidation_volume=long_liq_volume,
            short_liquidation_volume=short_liq_volume,
            total_liquidation_volume=total_volume,
            liquidation_count=len(raw_data),
        )

    async def close(self) -> None:
        """Close the client if owned."""
        if self._owns_client:
            await self.client.close()


def interpret_liquidation(liquidation: Liquidation) -> str:
    """Interpret liquidation data for LLM context.

    Args:
        liquidation: Liquidation data.

    Returns:
        Human-readable interpretation.
    """
    total = liquidation.total_liquidation_volume
    imbalance = liquidation.imbalance

    if total < 1.0:
        return "Low liquidation activity"
    elif total < 10.0:
        volume_level = "Moderate"
    elif total < 50.0:
        volume_level = "High"
    else:
        volume_level = "Extreme"

    if imbalance > 0.5:
        direction = "heavily biased to long liquidations (bearish)"
    elif imbalance > 0.2:
        direction = "more long liquidations (slightly bearish)"
    elif imbalance < -0.5:
        direction = "heavily biased to short liquidations (bullish)"
    elif imbalance < -0.2:
        direction = "more short liquidations (slightly bullish)"
    else:
        direction = "balanced"

    return f"{volume_level} liquidations, {direction}"
