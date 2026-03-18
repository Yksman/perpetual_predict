"""Tests for market data collectors."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from perpetual_predict.collectors.binance.market_data import (
    LongShortRatioCollector,
    OHLCVCollector,
)
from perpetual_predict.storage.models import Candle, LongShortRatio


class TestOHLCVCollector:
    """Tests for OHLCVCollector."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock BinanceClient."""
        client = MagicMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def sample_kline_data(self) -> list[list]:
        """Sample kline data from Binance API."""
        return [
            [
                1704067200000,  # Open time (2024-01-01 00:00:00 UTC)
                "42000.00",  # Open
                "43000.00",  # High
                "41000.00",  # Low
                "42500.00",  # Close
                "1000.00",  # Volume
                1704081599999,  # Close time
                "42500000.00",  # Quote volume
                5000,  # Number of trades
                "500.00",  # Taker buy base
                "21250000.00",  # Taker buy quote
                "0",  # Ignore
            ],
            [
                1704081600000,  # Open time (2024-01-01 04:00:00 UTC)
                "42500.00",
                "44000.00",
                "42000.00",
                "43500.00",
                "1500.00",
                1704095999999,
                "63750000.00",
                7500,
                "750.00",
                "31875000.00",
                "0",
            ],
        ]

    def test_init_with_defaults(self, mock_client: MagicMock) -> None:
        """Test collector initialization with defaults."""
        collector = OHLCVCollector(client=mock_client)
        assert collector.symbol == "BTCUSDT"
        assert collector.timeframe == "4h"
        assert collector.client is mock_client

    def test_init_with_custom_values(self, mock_client: MagicMock) -> None:
        """Test collector initialization with custom values."""
        collector = OHLCVCollector(
            client=mock_client,
            symbol="ETHUSDT",
            timeframe="1h",
        )
        assert collector.symbol == "ETHUSDT"
        assert collector.timeframe == "1h"

    @pytest.mark.asyncio
    async def test_collect_returns_candles(
        self, mock_client: MagicMock, sample_kline_data: list[list]
    ) -> None:
        """Test collect returns list of Candle objects."""
        mock_client.get_klines = AsyncMock(return_value=sample_kline_data)

        collector = OHLCVCollector(client=mock_client)
        candles = await collector.collect(limit=2)

        assert len(candles) == 2
        assert all(isinstance(c, Candle) for c in candles)

        # Check first candle
        assert candles[0].symbol == "BTCUSDT"
        assert candles[0].open == 42000.0
        assert candles[0].high == 43000.0
        assert candles[0].low == 41000.0
        assert candles[0].close == 42500.0
        assert candles[0].volume == 1000.0

    @pytest.mark.asyncio
    async def test_collect_with_time_range(
        self, mock_client: MagicMock, sample_kline_data: list[list]
    ) -> None:
        """Test collect with time range parameters."""
        mock_client.get_klines = AsyncMock(return_value=sample_kline_data)

        collector = OHLCVCollector(client=mock_client)
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        await collector.collect(start_time=start, end_time=end)

        mock_client.get_klines.assert_called_once()
        call_kwargs = mock_client.get_klines.call_args[1]
        assert call_kwargs["start_time"] == int(start.timestamp() * 1000)
        assert call_kwargs["end_time"] == int(end.timestamp() * 1000)

    def test_parse_kline(self, mock_client: MagicMock, sample_kline_data: list[list]) -> None:
        """Test kline parsing."""
        collector = OHLCVCollector(client=mock_client)
        candle = collector._parse_kline(sample_kline_data[0])

        assert candle.symbol == "BTCUSDT"
        assert candle.timeframe == "4h"
        assert candle.open == 42000.0
        assert candle.high == 43000.0
        assert candle.low == 41000.0
        assert candle.close == 42500.0
        assert candle.volume == 1000.0
        assert candle.trades == 5000
        assert candle.open_time.year == 2024

    @pytest.mark.asyncio
    async def test_close_owned_client(self) -> None:
        """Test close properly closes owned client."""
        collector = OHLCVCollector()
        collector.client.close = AsyncMock()
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_borrowed_client(self, mock_client: MagicMock) -> None:
        """Test close does not close borrowed client."""
        collector = OHLCVCollector(client=mock_client)
        await collector.close()
        mock_client.close.assert_not_called()


class TestLongShortRatioCollector:
    """Tests for LongShortRatioCollector."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock BinanceClient."""
        client = MagicMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def sample_ratio_data(self) -> list[dict]:
        """Sample long/short ratio data from Binance API."""
        return [
            {
                "symbol": "BTCUSDT",
                "longAccount": "0.55",
                "shortAccount": "0.45",
                "longShortRatio": "1.22",
                "timestamp": 1704067200000,  # 2024-01-01 00:00:00 UTC
            },
            {
                "symbol": "BTCUSDT",
                "longAccount": "0.52",
                "shortAccount": "0.48",
                "longShortRatio": "1.08",
                "timestamp": 1704081600000,
            },
        ]

    def test_init_with_defaults(self, mock_client: MagicMock) -> None:
        """Test collector initialization with defaults."""
        collector = LongShortRatioCollector(client=mock_client)
        assert collector.symbol == "BTCUSDT"
        assert collector.period == "4h"

    @pytest.mark.asyncio
    async def test_collect_returns_ratios(
        self, mock_client: MagicMock, sample_ratio_data: list[dict]
    ) -> None:
        """Test collect returns list of LongShortRatio objects."""
        mock_client.get_long_short_ratio = AsyncMock(return_value=sample_ratio_data)

        collector = LongShortRatioCollector(client=mock_client)
        ratios = await collector.collect(limit=2)

        assert len(ratios) == 2
        assert all(isinstance(r, LongShortRatio) for r in ratios)

        # Check first ratio
        assert ratios[0].symbol == "BTCUSDT"
        assert ratios[0].long_ratio == 0.55
        assert ratios[0].short_ratio == 0.45
        assert ratios[0].long_short_ratio == 1.22

    def test_parse_ratio(self, mock_client: MagicMock, sample_ratio_data: list[dict]) -> None:
        """Test ratio data parsing."""
        collector = LongShortRatioCollector(client=mock_client)
        ratio = collector._parse_ratio(sample_ratio_data[0])

        assert ratio.symbol == "BTCUSDT"
        assert ratio.long_ratio == 0.55
        assert ratio.short_ratio == 0.45
        assert ratio.long_short_ratio == 1.22
        assert ratio.timestamp.year == 2024
