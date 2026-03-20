"""Tests for scheduler Discord notifications."""

from unittest.mock import AsyncMock

import pytest

from perpetual_predict.notifications.scheduler_alerts import (
    send_collection_completed,
    send_collection_failed,
    send_collection_started,
)
from perpetual_predict.scheduler.health import HealthStatus, JobStatus


@pytest.fixture
def mock_webhook():
    """Create a mock Discord webhook."""
    webhook = AsyncMock()
    webhook.send_embed = AsyncMock(return_value={"ok": True})
    return webhook


@pytest.fixture
def sample_results():
    """Sample collection results."""
    return {
        "candles": 6,
        "funding_rates": 6,
        "open_interests": 6,
        "long_short_ratios": 6,
        "fear_greed": 1,
    }


@pytest.fixture
def health_status():
    """Sample health status with job history."""
    status = HealthStatus()
    status.jobs["collection"] = JobStatus(
        run_count=10,
        success_count=9,
        failure_count=1,
    )
    return status


class TestSendCollectionStarted:
    """Tests for send_collection_started."""

    @pytest.mark.asyncio
    async def test_sends_embed_with_correct_title(self, mock_webhook):
        """Should send embed with Korean title."""
        result = await send_collection_started(mock_webhook, "BTCUSDT", "4h")

        assert result is True
        mock_webhook.send_embed.assert_called_once()

        embed = mock_webhook.send_embed.call_args[0][0]
        assert "데이터 수집 시작" in embed.title

    @pytest.mark.asyncio
    async def test_includes_symbol_and_timeframe(self, mock_webhook):
        """Should include symbol and timeframe fields."""
        await send_collection_started(mock_webhook, "ETHUSDT", "1h")

        embed = mock_webhook.send_embed.call_args[0][0]
        field_names = [f["name"] for f in embed.fields]

        assert "심볼" in field_names
        assert "타임프레임" in field_names

    @pytest.mark.asyncio
    async def test_handles_webhook_failure_gracefully(self, mock_webhook):
        """Should return False and not raise on webhook failure."""
        mock_webhook.send_embed.side_effect = Exception("Network error")

        result = await send_collection_started(mock_webhook, "BTCUSDT", "4h")

        assert result is False


class TestSendCollectionCompleted:
    """Tests for send_collection_completed."""

    @pytest.mark.asyncio
    async def test_sends_success_embed(self, mock_webhook, sample_results):
        """Should send green success embed."""
        result = await send_collection_completed(
            mock_webhook, sample_results, 5.5, symbol="BTCUSDT"
        )

        assert result is True
        embed = mock_webhook.send_embed.call_args[0][0]
        assert "완료" in embed.title

    @pytest.mark.asyncio
    async def test_includes_record_counts(self, mock_webhook, sample_results):
        """Should include all record counts in results."""
        await send_collection_completed(
            mock_webhook, sample_results, 5.5, symbol="BTCUSDT"
        )

        embed = mock_webhook.send_embed.call_args[0][0]
        results_field = next(f for f in embed.fields if "결과" in f["name"])

        assert "캔들" in results_field["value"]
        assert "펀딩" in results_field["value"]
        assert "미결제약정" in results_field["value"]

    @pytest.mark.asyncio
    async def test_includes_health_status_when_provided(
        self, mock_webhook, sample_results, health_status
    ):
        """Should include job statistics from health status."""
        await send_collection_completed(
            mock_webhook, sample_results, 5.5, health_status, "BTCUSDT"
        )

        embed = mock_webhook.send_embed.call_args[0][0]
        field_names = [f["name"] for f in embed.fields]

        assert any("통계" in name for name in field_names)

    @pytest.mark.asyncio
    async def test_calculates_total_records(self, mock_webhook, sample_results):
        """Should calculate and display total record count."""
        await send_collection_completed(
            mock_webhook, sample_results, 5.5, symbol="BTCUSDT"
        )

        embed = mock_webhook.send_embed.call_args[0][0]
        total_field = next(f for f in embed.fields if "총 레코드" in f["name"])

        # 6+6+6+6+1 = 25
        assert "25" in total_field["value"]


class TestSendCollectionFailed:
    """Tests for send_collection_failed."""

    @pytest.mark.asyncio
    async def test_sends_error_embed(self, mock_webhook):
        """Should send red error embed."""
        result = await send_collection_failed(
            mock_webhook, "Connection timeout", 10.0, symbol="BTCUSDT"
        )

        assert result is True
        embed = mock_webhook.send_embed.call_args[0][0]
        assert "실패" in embed.title

    @pytest.mark.asyncio
    async def test_includes_error_message(self, mock_webhook):
        """Should include error message in embed."""
        error_msg = "API rate limit exceeded"
        await send_collection_failed(mock_webhook, error_msg, 10.0, symbol="BTCUSDT")

        embed = mock_webhook.send_embed.call_args[0][0]
        error_field = next(f for f in embed.fields if "오류" in f["name"])

        assert error_msg in error_field["value"]

    @pytest.mark.asyncio
    async def test_truncates_long_error_messages(self, mock_webhook):
        """Should truncate error messages over 1000 chars."""
        long_error = "x" * 2000
        await send_collection_failed(mock_webhook, long_error, 10.0, symbol="BTCUSDT")

        embed = mock_webhook.send_embed.call_args[0][0]
        error_field = next(f for f in embed.fields if "오류" in f["name"])

        # 1000 chars + code block markdown (```\n...\n```) = ~1010
        assert len(error_field["value"]) < 1020

    @pytest.mark.asyncio
    async def test_includes_failure_count_from_health_status(
        self, mock_webhook, health_status
    ):
        """Should include failure count when health status provided."""
        await send_collection_failed(
            mock_webhook, "Error", 10.0, health_status, "BTCUSDT"
        )

        embed = mock_webhook.send_embed.call_args[0][0]
        field_names = [f["name"] for f in embed.fields]

        assert any("실패 통계" in name for name in field_names)

    @pytest.mark.asyncio
    async def test_handles_webhook_failure_gracefully(self, mock_webhook):
        """Should return False and not raise on webhook failure."""
        mock_webhook.send_embed.side_effect = Exception("Network error")

        result = await send_collection_failed(
            mock_webhook, "Some error", 10.0, symbol="BTCUSDT"
        )

        assert result is False
