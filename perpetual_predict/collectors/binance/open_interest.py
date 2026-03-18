"""Open interest collector for Binance Futures API."""

from datetime import datetime, timezone
from typing import Any

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import OpenInterest
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class OpenInterestCollector(BaseCollector):
    """Collector for open interest data."""

    def __init__(
        self,
        client: BinanceClient | None = None,
        symbol: str | None = None,
        period: str = "4h",
    ):
        """Initialize open interest collector.

        Args:
            client: BinanceClient instance. If None, creates a new one.
            symbol: Trading pair symbol. If None, uses settings.
            period: Data period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d).
        """
        self.client = client or BinanceClient()
        self._owns_client = client is None

        settings = get_settings()
        self.symbol = symbol or settings.trading.symbol
        self.period = period

    async def collect(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 30,
        **kwargs: Any,
    ) -> list[OpenInterest]:
        """Collect open interest history data.

        Args:
            start_time: Start time for data collection.
            end_time: End time for data collection.
            limit: Maximum number of records to collect.
            **kwargs: Additional arguments (ignored).

        Returns:
            List of OpenInterest objects.
        """
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None

        logger.info(
            f"Collecting OI history for {self.symbol} {self.period}, limit={limit}"
        )

        raw_data = await self.client.get_open_interest_hist(
            symbol=self.symbol,
            period=self.period,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )

        ois = [self._parse_open_interest(data) for data in raw_data]
        logger.info(f"Collected {len(ois)} OI history records")

        return ois

    def _parse_open_interest(self, data: dict[str, Any]) -> OpenInterest:
        """Parse raw OI data into OpenInterest object.

        Data format from Binance:
        {
            "symbol": "BTCUSDT",
            "sumOpenInterest": "100000.00",
            "sumOpenInterestValue": "4200000000.00",
            "timestamp": 1234567890000
        }
        """
        return OpenInterest(
            symbol=data["symbol"],
            timestamp=datetime.fromtimestamp(data["timestamp"] / 1000, tz=timezone.utc),
            open_interest=float(data["sumOpenInterest"]),
            open_interest_value=float(data["sumOpenInterestValue"]),
        )

    async def collect_current(self) -> OpenInterest:
        """Collect the current open interest.

        Returns:
            Current OpenInterest.
        """
        logger.info(f"Collecting current OI for {self.symbol}")

        raw_data = await self.client.get_open_interest(self.symbol)

        return OpenInterest(
            symbol=raw_data["symbol"],
            timestamp=datetime.now(timezone.utc),
            open_interest=float(raw_data["openInterest"]),
            open_interest_value=0.0,  # Current OI endpoint doesn't provide value
        )

    async def close(self) -> None:
        """Close the client if owned."""
        if self._owns_client:
            await self.client.close()
