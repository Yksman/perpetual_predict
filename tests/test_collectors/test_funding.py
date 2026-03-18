"""Tests for funding rate collector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from perpetual_predict.collectors.binance.funding import FundingRateCollector
from perpetual_predict.storage.models import FundingRate


class TestFundingRateCollector:
    """Tests for FundingRateCollector."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock BinanceClient."""
        client = MagicMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def sample_funding_data(self) -> list[dict]:
        """Sample funding rate data from Binance API."""
        return [
            {
                "symbol": "BTCUSDT",
                "fundingTime": 1704067200000,  # 2024-01-01 00:00:00 UTC
                "fundingRate": "0.0001",
                "markPrice": "42000.00",
            },
            {
                "symbol": "BTCUSDT",
                "fundingTime": 1704096000000,  # 2024-01-01 08:00:00 UTC
                "fundingRate": "-0.0002",
                "markPrice": "41500.00",
            },
        ]

    @pytest.fixture
    def sample_mark_price_data(self) -> dict:
        """Sample mark price data from Binance API."""
        return {
            "symbol": "BTCUSDT",
            "markPrice": "42500.00",
            "indexPrice": "42480.00",
            "lastFundingRate": "0.00015",
            "time": 1704110400000,
        }

    def test_init_with_defaults(self, mock_client: MagicMock) -> None:
        """Test collector initialization with defaults."""
        collector = FundingRateCollector(client=mock_client)
        assert collector.symbol == "BTCUSDT"
        assert collector.client is mock_client

    def test_init_with_custom_symbol(self, mock_client: MagicMock) -> None:
        """Test collector initialization with custom symbol."""
        collector = FundingRateCollector(client=mock_client, symbol="ETHUSDT")
        assert collector.symbol == "ETHUSDT"

    @pytest.mark.asyncio
    async def test_collect_returns_funding_rates(
        self,
        mock_client: MagicMock,
        sample_funding_data: list[dict],
        sample_mark_price_data: dict,
    ) -> None:
        """Test collect returns list of FundingRate objects."""
        mock_client.get_funding_rate = AsyncMock(return_value=sample_funding_data)
        mock_client.get_mark_price = AsyncMock(return_value=sample_mark_price_data)

        collector = FundingRateCollector(client=mock_client)
        rates = await collector.collect(limit=2)

        assert len(rates) == 2
        assert all(isinstance(r, FundingRate) for r in rates)

        # Check first rate
        assert rates[0].symbol == "BTCUSDT"
        assert rates[0].funding_rate == 0.0001
        assert rates[0].mark_price == 42000.0

    @pytest.mark.asyncio
    async def test_collect_with_time_range(
        self,
        mock_client: MagicMock,
        sample_funding_data: list[dict],
        sample_mark_price_data: dict,
    ) -> None:
        """Test collect with time range parameters."""
        mock_client.get_funding_rate = AsyncMock(return_value=sample_funding_data)
        mock_client.get_mark_price = AsyncMock(return_value=sample_mark_price_data)

        collector = FundingRateCollector(client=mock_client)
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        await collector.collect(start_time=start, end_time=end)

        mock_client.get_funding_rate.assert_called_once()
        call_kwargs = mock_client.get_funding_rate.call_args[1]
        assert call_kwargs["start_time"] == int(start.timestamp() * 1000)
        assert call_kwargs["end_time"] == int(end.timestamp() * 1000)

    def test_parse_funding_rate(
        self,
        mock_client: MagicMock,
        sample_funding_data: list[dict],
        sample_mark_price_data: dict,
    ) -> None:
        """Test funding rate parsing."""
        collector = FundingRateCollector(client=mock_client)
        rate = collector._parse_funding_rate(
            sample_funding_data[0], sample_mark_price_data
        )

        assert rate.symbol == "BTCUSDT"
        assert rate.funding_rate == 0.0001
        assert rate.mark_price == 42000.0
        assert rate.funding_time.year == 2024

    def test_parse_funding_rate_negative(
        self,
        mock_client: MagicMock,
        sample_funding_data: list[dict],
        sample_mark_price_data: dict,
    ) -> None:
        """Test parsing negative funding rate."""
        collector = FundingRateCollector(client=mock_client)
        rate = collector._parse_funding_rate(
            sample_funding_data[1], sample_mark_price_data
        )

        assert rate.funding_rate == -0.0002

    @pytest.mark.asyncio
    async def test_collect_current(
        self, mock_client: MagicMock, sample_mark_price_data: dict
    ) -> None:
        """Test collecting current funding rate."""
        mock_client.get_mark_price = AsyncMock(return_value=sample_mark_price_data)

        collector = FundingRateCollector(client=mock_client)
        rate = await collector.collect_current()

        assert rate is not None
        assert rate.symbol == "BTCUSDT"
        assert rate.funding_rate == 0.00015
        assert rate.mark_price == 42500.0

    @pytest.mark.asyncio
    async def test_collect_current_no_data(self, mock_client: MagicMock) -> None:
        """Test collecting current funding rate when no data available."""
        mock_client.get_mark_price = AsyncMock(
            return_value={"symbol": "BTCUSDT", "markPrice": "42000.00"}
        )

        collector = FundingRateCollector(client=mock_client)
        rate = await collector.collect_current()

        assert rate is None

    @pytest.mark.asyncio
    async def test_close_owned_client(self) -> None:
        """Test close properly closes owned client."""
        collector = FundingRateCollector()
        collector.client.close = AsyncMock()
        await collector.close()
        collector.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_borrowed_client(self, mock_client: MagicMock) -> None:
        """Test close does not close borrowed client."""
        collector = FundingRateCollector(client=mock_client)
        await collector.close()
        mock_client.close.assert_not_called()
