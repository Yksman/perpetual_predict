"""Market data collectors for Binance Futures API."""

from datetime import datetime, timezone
from typing import Any

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.binance.client import BinanceClient
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import Candle, LongShortRatio
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class OHLCVCollector(BaseCollector):
    """Collector for OHLCV candlestick data."""

    def __init__(
        self,
        client: BinanceClient | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
    ):
        """Initialize OHLCV collector.

        Args:
            client: BinanceClient instance. If None, creates a new one.
            symbol: Trading pair symbol. If None, uses settings.
            timeframe: Candle timeframe. If None, uses settings.
        """
        self.client = client or BinanceClient()
        self._owns_client = client is None

        settings = get_settings()
        self.symbol = symbol or settings.trading.symbol
        self.timeframe = timeframe or settings.trading.timeframe

    async def collect(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
        **kwargs: Any,
    ) -> list[Candle]:
        """Collect OHLCV candlestick data.

        Args:
            start_time: Start time for data collection.
            end_time: End time for data collection.
            limit: Maximum number of candles to collect.
            **kwargs: Additional arguments (ignored).

        Returns:
            List of Candle objects.
        """
        # Convert datetime to milliseconds timestamp
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None

        logger.info(
            f"Collecting OHLCV for {self.symbol} {self.timeframe}, limit={limit}"
        )

        raw_data = await self.client.get_klines(
            symbol=self.symbol,
            interval=self.timeframe,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )

        candles = [self._parse_kline(kline) for kline in raw_data]
        logger.info(f"Collected {len(candles)} candles")

        return candles

    def _parse_kline(self, kline: list[Any]) -> Candle:
        """Parse raw kline data into Candle object.

        Kline format from Binance:
        [
            0: Open time (ms),
            1: Open,
            2: High,
            3: Low,
            4: Close,
            5: Volume,
            6: Close time (ms),
            7: Quote asset volume,
            8: Number of trades,
            9: Taker buy base asset volume,
            10: Taker buy quote asset volume,
            11: Ignore
        ]
        """
        return Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open_time=datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
            open=float(kline[1]),
            high=float(kline[2]),
            low=float(kline[3]),
            close=float(kline[4]),
            volume=float(kline[5]),
            close_time=datetime.fromtimestamp(kline[6] / 1000, tz=timezone.utc),
            quote_volume=float(kline[7]),
            trades=int(kline[8]),
            taker_buy_base=float(kline[9]),
            taker_buy_quote=float(kline[10]),
        )

    async def close(self) -> None:
        """Close the client if owned."""
        if self._owns_client:
            await self.client.close()


class LongShortRatioCollector(BaseCollector):
    """Collector for long/short ratio data."""

    def __init__(
        self,
        client: BinanceClient | None = None,
        symbol: str | None = None,
        period: str = "4h",
    ):
        """Initialize Long/Short ratio collector.

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
    ) -> list[LongShortRatio]:
        """Collect long/short ratio data.

        Args:
            start_time: Start time for data collection.
            end_time: End time for data collection.
            limit: Maximum number of records to collect.
            **kwargs: Additional arguments (ignored).

        Returns:
            List of LongShortRatio objects.
        """
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None

        logger.info(
            f"Collecting Long/Short ratio for {self.symbol} {self.period}, limit={limit}"
        )

        raw_data = await self.client.get_long_short_ratio(
            symbol=self.symbol,
            period=self.period,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )

        ratios = [self._parse_ratio(data) for data in raw_data]
        logger.info(f"Collected {len(ratios)} long/short ratio records")

        return ratios

    def _parse_ratio(self, data: dict[str, Any]) -> LongShortRatio:
        """Parse raw ratio data into LongShortRatio object.

        Data format from Binance:
        {
            "symbol": "BTCUSDT",
            "longAccount": "0.5",
            "shortAccount": "0.5",
            "longShortRatio": "1.0",
            "timestamp": 1234567890000
        }
        """
        return LongShortRatio(
            symbol=data["symbol"],
            timestamp=datetime.fromtimestamp(data["timestamp"] / 1000, tz=timezone.utc),
            long_ratio=float(data["longAccount"]),
            short_ratio=float(data["shortAccount"]),
            long_short_ratio=float(data["longShortRatio"]),
        )

    async def close(self) -> None:
        """Close the client if owned."""
        if self._owns_client:
            await self.client.close()
