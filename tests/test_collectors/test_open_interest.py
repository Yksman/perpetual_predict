"""Tests for open interest collector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from perpetual_predict.collectors.binance.open_interest import OpenInterestCollector
from perpetual_predict.storage.models import OpenInterest


class TestOpenInterestCollector:
    """Tests for OpenInterestCollector."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock BinanceClient."""
        client = MagicMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def sample_oi_history_data(self) -> list[dict]:
        """Sample open interest history data from Binance API."""
        return [
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "100000.00",
                "sumOpenInterestValue": "4200000000.00",
                "timestamp": 1704067200000,  # 2024-01-01 00:00:00 UTC
            },
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "105000.00",
                "sumOpenInterestValue": "4410000000.00",
                "timestamp": 1704081600000,
            },
        ]

    @pytest.fixture
    def sample_current_oi_data(self) -> dict:
        """Sample current open interest data from Binance API."""
        return {
            "symbol": "BTCUSDT",
            "openInterest": "110000.00",
            "time": 1704096000000,
        }

    def test_init_with_defaults(self, mock_client: MagicMock) -> None:
        """Test collector initialization with defaults."""
        collector = OpenInterestCollector(client=mock_client)
        assert collector.symbol == "BTCUSDT"
        assert collector.period == "4h"
        assert collector.client is mock_client

    def test_init_with_custom_values(self, mock_client: MagicMock) -> None:
        """Test collector initialization with custom values."""
        collector = OpenInterestCollector(
            client=mock_client,
            symbol="ETHUSDT",
            period="1h",
        )
        assert collector.symbol == "ETHUSDT"
        assert collector.period == "1h"

    @pytest.mark.asyncio
    async def test_collect_returns_oi_list(
        self, mock_client: MagicMock, sample_oi_history_data: list[dict]
    ) -> None:
        """Test collect returns list of OpenInterest objects."""
        mock_client.get_open_interest_hist = AsyncMock(
            return_value=sample_oi_history_data
        )

        collector = OpenInterestCollector(client=mock_client)
        ois = await collector.collect(limit=2)

        assert len(ois) == 2
        assert all(isinstance(oi, OpenInterest) for oi in ois)

        # Check first OI
        assert ois[0].symbol == "BTCUSDT"
        assert ois[0].open_interest == 100000.0
        assert ois[0].open_interest_value == 4200000000.0

    @pytest.mark.asyncio
    async def test_collect_with_time_range(
        self, mock_client: MagicMock, sample_oi_history_data: list[dict]
    ) -> None:
        """Test collect with time range parameters."""
        mock_client.get_open_interest_hist = AsyncMock(
            return_value=sample_oi_history_data
        )

        collector = OpenInterestCollector(client=mock_client)
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        await collector.collect(start_time=start, end_time=end)

        mock_client.get_open_interest_hist.assert_called_once()
        call_kwargs = mock_client.get_open_interest_hist.call_args[1]
        assert call_kwargs["start_time"] == int(start.timestamp() * 1000)
        assert call_kwargs["end_time"] == int(end.timestamp() * 1000)

    def test_parse_open_interest(
        self, mock_client: MagicMock, sample_oi_history_data: list[dict]
    ) -> None:
        """Test OI data parsing."""
        collector = OpenInterestCollector(client=mock_client)
        oi = collector._parse_open_interest(sample_oi_history_data[0])

        assert oi.symbol == "BTCUSDT"
        assert oi.open_interest == 100000.0
        assert oi.open_interest_value == 4200000000.0
        assert oi.timestamp.year == 2024

    @pytest.mark.asyncio
    async def test_collect_current(
        self, mock_client: MagicMock, sample_current_oi_data: dict
    ) -> None:
        """Test collecting current open interest."""
        mock_client.get_open_interest = AsyncMock(return_value=sample_current_oi_data)

        collector = OpenInterestCollector(client=mock_client)
        oi = await collector.collect_current()

        assert oi.symbol == "BTCUSDT"
        assert oi.open_interest == 110000.0
        assert oi.open_interest_value == 0.0  # Current endpoint doesn't provide value

    @pytest.mark.asyncio
    async def test_close_owned_client(self) -> None:
        """Test close properly closes owned client."""
        collector = OpenInterestCollector()
        collector.client.close = AsyncMock()
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_borrowed_client(self, mock_client: MagicMock) -> None:
        """Test close does not close borrowed client."""
        collector = OpenInterestCollector(client=mock_client)
        await collector.close()
        mock_client.close.assert_not_called()
