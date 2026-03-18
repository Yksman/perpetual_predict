"""Funding rate collector for Binance Futures API."""

from datetime import datetime, timezone
from typing import Any

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import FundingRate
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class FundingRateCollector(BaseCollector):
    """Collector for funding rate data."""

    def __init__(
        self,
        client: BinanceClient | None = None,
        symbol: str | None = None,
    ):
        """Initialize funding rate collector.

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
    ) -> list[FundingRate]:
        """Collect funding rate data.

        Args:
            start_time: Start time for data collection.
            end_time: End time for data collection.
            limit: Maximum number of records to collect.
            **kwargs: Additional arguments (ignored).

        Returns:
            List of FundingRate objects.
        """
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None

        logger.info(f"Collecting funding rates for {self.symbol}, limit={limit}")

        raw_data = await self.client.get_funding_rate(
            symbol=self.symbol,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )

        # Also get current mark price for the latest rate
        mark_price_data = await self.client.get_mark_price(self.symbol)

        rates = [self._parse_funding_rate(data, mark_price_data) for data in raw_data]
        logger.info(f"Collected {len(rates)} funding rate records")

        return rates

    def _parse_funding_rate(
        self,
        data: dict[str, Any],
        mark_price_data: dict[str, Any],
    ) -> FundingRate:
        """Parse raw funding rate data into FundingRate object.

        Data format from Binance:
        {
            "symbol": "BTCUSDT",
            "fundingTime": 1234567890000,
            "fundingRate": "0.0001",
            "markPrice": "42000.00"  // May not always be present
        }

        Mark price data format:
        {
            "symbol": "BTCUSDT",
            "markPrice": "42000.00",
            "indexPrice": "42000.00",
            ...
        }
        """
        # Get mark price from the funding rate data if available,
        # otherwise use the current mark price
        mark_price = float(data.get("markPrice", mark_price_data.get("markPrice", 0)))

        return FundingRate(
            symbol=data["symbol"],
            funding_time=datetime.fromtimestamp(
                data["fundingTime"] / 1000, tz=timezone.utc
            ),
            funding_rate=float(data["fundingRate"]),
            mark_price=mark_price,
        )

    async def collect_current(self) -> FundingRate | None:
        """Collect the current funding rate.

        Returns:
            Current FundingRate or None if unavailable.
        """
        logger.info(f"Collecting current funding rate for {self.symbol}")

        mark_price_data = await self.client.get_mark_price(self.symbol)

        if "lastFundingRate" not in mark_price_data:
            logger.warning("No funding rate data available")
            return None

        return FundingRate(
            symbol=mark_price_data["symbol"],
            funding_time=datetime.fromtimestamp(
                int(mark_price_data.get("time", 0)) / 1000, tz=timezone.utc
            ),
            funding_rate=float(mark_price_data["lastFundingRate"]),
            mark_price=float(mark_price_data["markPrice"]),
        )

    async def close(self) -> None:
        """Close the client if owned."""
        if self._owns_client:
            await self.client.close()
