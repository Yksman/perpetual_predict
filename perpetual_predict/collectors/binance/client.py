"""Binance Futures API client."""

import hashlib
import hmac
import time
from typing import Any

import aiohttp

from perpetual_predict.config import get_settings
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class BinanceAPIError(Exception):
    """Exception raised for Binance API errors."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error {code}: {message}")


class BinanceClient:
    """Async client for Binance Futures API.

    Handles authentication, request signing, and rate limiting.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        use_testnet: bool | None = None,
    ):
        """Initialize Binance client.

        Args:
            api_key: Binance API key. If None, uses settings.
            api_secret: Binance API secret. If None, uses settings.
            use_testnet: Whether to use testnet. If None, uses settings.
        """
        settings = get_settings()

        self.api_key = api_key or settings.binance.api_key
        self.api_secret = api_secret or settings.binance.api_secret

        if use_testnet is None:
            use_testnet = settings.binance.use_testnet
        self.base_url = (
            settings.binance.testnet_url if use_testnet else settings.binance.base_url
        )

        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create the HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self.api_key} if self.api_key else {}
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _sign_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Sign request parameters with HMAC SHA256.

        Args:
            params: Request parameters to sign.

        Returns:
            Parameters with signature added.
        """
        if not self.api_secret:
            return params

        # Add timestamp
        params["timestamp"] = int(time.time() * 1000)

        # Create query string
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))

        # Generate signature
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        params["signature"] = signature
        return params

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            params: Query parameters.
            signed: Whether to sign the request.

        Returns:
            JSON response data.

        Raises:
            BinanceAPIError: If API returns an error.
            aiohttp.ClientError: If request fails.
        """
        params = params or {}

        if signed:
            params = self._sign_request(params)

        url = f"{self.base_url}{endpoint}"

        logger.debug(f"Request: {method} {url}")

        async with self.session.request(method, url, params=params) as response:
            data = await response.json()

            # Check for API errors
            if isinstance(data, dict) and "code" in data and "msg" in data:
                raise BinanceAPIError(data["code"], data["msg"])

            if response.status != 200:
                raise BinanceAPIError(
                    response.status, f"HTTP Error: {response.reason}"
                )

            return data

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        """Make a GET request.

        Args:
            endpoint: API endpoint path.
            params: Query parameters.
            signed: Whether to sign the request.

        Returns:
            JSON response data.
        """
        return await self._request("GET", endpoint, params, signed)

    # Public API endpoints
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 500,
    ) -> list[list[Any]]:
        """Get kline/candlestick data.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT").
            interval: Kline interval (e.g., "4h", "1d").
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.
            limit: Number of candles to return (max 1500).

        Returns:
            List of kline data arrays.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1500),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.get("/fapi/v1/klines", params)

    async def get_funding_rate(
        self,
        symbol: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get funding rate history.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT").
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.
            limit: Number of records to return (max 1000).

        Returns:
            List of funding rate records.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "limit": min(limit, 1000),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.get("/fapi/v1/fundingRate", params)

    async def get_open_interest(self, symbol: str) -> dict[str, Any]:
        """Get current open interest.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT").

        Returns:
            Open interest data.
        """
        return await self.get("/fapi/v1/openInterest", {"symbol": symbol})

    async def get_open_interest_hist(
        self,
        symbol: str,
        period: str = "4h",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get open interest history.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT").
            period: Data period ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d").
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.
            limit: Number of records to return (max 500).

        Returns:
            List of open interest history records.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "period": period,
            "limit": min(limit, 500),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.get("/futures/data/openInterestHist", params)

    async def get_long_short_ratio(
        self,
        symbol: str,
        period: str = "4h",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get top trader long/short ratio (accounts).

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT").
            period: Data period ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d").
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.
            limit: Number of records to return (max 500).

        Returns:
            List of long/short ratio records.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "period": period,
            "limit": min(limit, 500),
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.get("/futures/data/topLongShortAccountRatio", params)

    async def get_mark_price(self, symbol: str) -> dict[str, Any]:
        """Get current mark price and funding rate.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT").

        Returns:
            Mark price and funding rate data.
        """
        return await self.get("/fapi/v1/premiumIndex", {"symbol": symbol})

    async def get_force_orders(
        self,
        symbol: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get liquidation (force order) history.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT"). If None, returns all.
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.
            limit: Number of records to return (max 1000).

        Returns:
            List of liquidation order records.
        """
        params: dict[str, Any] = {
            "limit": min(limit, 1000),
        }

        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self.get("/fapi/v1/allForceOrders", params)
