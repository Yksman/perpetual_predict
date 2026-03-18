"""Tests for Binance API client."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from perpetual_predict.collectors.binance import BinanceAPIError, BinanceClient


class TestBinanceClient:
    """Tests for BinanceClient."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default settings."""
        with patch.dict(os.environ, {}, clear=True):
            client = BinanceClient()
            assert client.api_key == ""
            assert client.api_secret == ""
            assert "fapi.binance.com" in client.base_url

    def test_init_with_custom_values(self) -> None:
        """Test client initialization with custom values."""
        client = BinanceClient(
            api_key="test_key",
            api_secret="test_secret",
            use_testnet=True,
        )
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert "testnet" in client.base_url

    def test_sign_request_adds_timestamp(self) -> None:
        """Test request signing adds timestamp."""
        client = BinanceClient(api_key="key", api_secret="secret")
        params = {"symbol": "BTCUSDT"}
        signed = client._sign_request(params)

        assert "timestamp" in signed
        assert "signature" in signed

    def test_sign_request_without_secret(self) -> None:
        """Test request signing without secret returns original params."""
        client = BinanceClient(api_key="key", api_secret="")
        params = {"symbol": "BTCUSDT"}
        signed = client._sign_request(params)

        assert "timestamp" not in signed
        assert "signature" not in signed

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        """Test closing client session."""
        client = BinanceClient()
        # Access session to create it
        _ = client.session
        assert client._session is not None

        await client.close()
        assert client._session is None


class TestBinanceAPIError:
    """Tests for BinanceAPIError."""

    def test_error_message(self) -> None:
        """Test error message formatting."""
        error = BinanceAPIError(code=-1121, message="Invalid symbol")
        assert "-1121" in str(error)
        assert "Invalid symbol" in str(error)

    def test_error_attributes(self) -> None:
        """Test error attributes."""
        error = BinanceAPIError(code=-1000, message="Unknown error")
        assert error.code == -1000
        assert error.message == "Unknown error"


class TestBinanceClientMockedRequests:
    """Tests for BinanceClient with mocked HTTP requests."""

    @pytest.mark.asyncio
    async def test_get_klines_params(self) -> None:
        """Test get_klines sends correct parameters."""
        client = BinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[[1, 2, 3, 4, 5]])

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=None)

            await client.get_klines("BTCUSDT", "4h", limit=100)

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert "/fapi/v1/klines" in call_args[0][1]
            assert call_args[1]["params"]["symbol"] == "BTCUSDT"
            assert call_args[1]["params"]["interval"] == "4h"
            assert call_args[1]["params"]["limit"] == 100

        await client.close()

    @pytest.mark.asyncio
    async def test_get_funding_rate_params(self) -> None:
        """Test get_funding_rate sends correct parameters."""
        client = BinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"fundingRate": "0.0001"}])

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=None)

            await client.get_funding_rate("BTCUSDT", limit=50)

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["params"]["symbol"] == "BTCUSDT"
            assert call_args[1]["params"]["limit"] == 50

        await client.close()

    @pytest.mark.asyncio
    async def test_api_error_handling(self) -> None:
        """Test API error response handling."""
        client = BinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"code": -1121, "msg": "Invalid symbol"}
        )

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(BinanceAPIError) as exc_info:
                await client.get_klines("INVALID", "4h")

            assert exc_info.value.code == -1121

        await client.close()

    @pytest.mark.asyncio
    async def test_limit_capping(self) -> None:
        """Test that limit parameters are capped."""
        client = BinanceClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=None)

            # Request more than max limit
            await client.get_klines("BTCUSDT", "4h", limit=2000)

            # Should be capped to 1500
            call_args = mock_request.call_args
            assert call_args[1]["params"]["limit"] == 1500

        await client.close()
