"""Tests for Fear & Greed Index collector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from perpetual_predict.collectors.sentiment.fear_greed import FearGreedCollector
from perpetual_predict.storage.models import FearGreedIndex


class TestFearGreedCollector:
    """Tests for FearGreedCollector."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock aiohttp session."""
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()
        return session

    @pytest.fixture
    def sample_fgi_data(self) -> dict:
        """Sample Fear & Greed Index API response."""
        return {
            "name": "Fear and Greed Index",
            "data": [
                {
                    "value": "25",
                    "value_classification": "Extreme Fear",
                    "timestamp": "1704067200",  # 2024-01-01 00:00:00 UTC
                    "time_until_update": "42000",
                },
                {
                    "value": "50",
                    "value_classification": "Neutral",
                    "timestamp": "1703980800",  # 2023-12-31 00:00:00 UTC
                    "time_until_update": "0",
                },
            ],
            "metadata": {"error": None},
        }

    def test_init_with_session(self, mock_session: MagicMock) -> None:
        """Test collector initialization with provided session."""
        collector = FearGreedCollector(session=mock_session)
        assert collector._session is mock_session
        assert collector._owns_session is False

    def test_init_without_session(self) -> None:
        """Test collector initialization without session."""
        collector = FearGreedCollector()
        assert collector._session is None
        assert collector._owns_session is True

    @pytest.mark.asyncio
    async def test_collect_returns_fgi_list(
        self, mock_session: MagicMock, sample_fgi_data: dict
    ) -> None:
        """Test collect returns list of FearGreedIndex objects."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=sample_fgi_data)
        mock_session.get = MagicMock(
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        collector = FearGreedCollector(session=mock_session)
        results = await collector.collect(limit=2)

        assert len(results) == 2
        assert all(isinstance(r, FearGreedIndex) for r in results)

        # Check first result
        assert results[0].value == 25
        assert results[0].classification == "Extreme Fear"

    @pytest.mark.asyncio
    async def test_collect_current(
        self, mock_session: MagicMock, sample_fgi_data: dict
    ) -> None:
        """Test collecting current Fear & Greed Index."""
        # Return only first item
        current_data = {
            "data": [sample_fgi_data["data"][0]],
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=current_data)
        mock_session.get = MagicMock(
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        collector = FearGreedCollector(session=mock_session)
        result = await collector.collect_current()

        assert result is not None
        assert result.value == 25
        assert result.classification == "Extreme Fear"

    @pytest.mark.asyncio
    async def test_collect_current_empty(self, mock_session: MagicMock) -> None:
        """Test collect_current when no data available."""
        empty_data = {"data": []}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=empty_data)
        mock_session.get = MagicMock(
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        collector = FearGreedCollector(session=mock_session)
        result = await collector.collect_current()

        assert result is None

    def test_parse_fear_greed(self, mock_session: MagicMock) -> None:
        """Test parsing Fear & Greed Index data."""
        collector = FearGreedCollector(session=mock_session)
        data = {
            "value": "75",
            "value_classification": "Greed",
            "timestamp": "1704067200",
        }

        result = collector._parse_fear_greed(data)

        assert result.value == 75
        assert result.classification == "Greed"
        assert result.timestamp == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_close_owned_session(self) -> None:
        """Test close properly closes owned session."""
        collector = FearGreedCollector()
        # Create session
        _ = collector.session
        collector._session.close = AsyncMock()
        await collector.close()
        collector._session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_borrowed_session(self, mock_session: MagicMock) -> None:
        """Test close does not close borrowed session."""
        collector = FearGreedCollector(session=mock_session)
        await collector.close()
        mock_session.close.assert_not_called()
