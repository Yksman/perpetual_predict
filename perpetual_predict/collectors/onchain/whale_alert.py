"""Whale Alert API collector for large cryptocurrency transactions."""

from datetime import datetime, timezone
from typing import Any

import aiohttp

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import WhaleTransaction
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class WhaleAlertCollector(BaseCollector):
    """Collector for large cryptocurrency transactions from Whale Alert API.

    Whale Alert tracks large-scale cryptocurrency movements including:
    - Exchange deposits/withdrawals
    - Wallet-to-wallet transfers
    - Mint/burn operations
    """

    def __init__(
        self,
        api_key: str | None = None,
        min_value_usd: int | None = None,
        currency: str = "btc",
    ):
        """Initialize Whale Alert collector.

        Args:
            api_key: Whale Alert API key. If None, uses settings.
            min_value_usd: Minimum transaction value in USD.
            currency: Cryptocurrency to track (e.g., "btc", "eth").
        """
        settings = get_settings()
        wa_config = settings.whale_alert

        self.api_key = api_key or wa_config.api_key
        self.base_url = wa_config.base_url
        self.min_value_usd = min_value_usd or wa_config.min_value_usd
        self.currency = currency.lower()

        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def collect(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> list[WhaleTransaction]:
        """Collect whale transactions.

        Args:
            start_time: Start time for data collection.
            end_time: End time for data collection.
            limit: Maximum number of records (API max: 100).
            **kwargs: Additional arguments (ignored).

        Returns:
            List of WhaleTransaction objects.
        """
        if not self.api_key:
            logger.warning("Whale Alert API key not configured, skipping collection")
            return []

        # Default to last hour if no time range specified
        now = datetime.now(timezone.utc)
        if end_time is None:
            end_time = now
        if start_time is None:
            start_time = datetime.fromtimestamp(
                end_time.timestamp() - 3600, tz=timezone.utc
            )

        logger.info(
            f"Collecting whale transactions for {self.currency}, "
            f"min_value=${self.min_value_usd:,}"
        )

        params = {
            "api_key": self.api_key,
            "min_value": self.min_value_usd,
            "start": int(start_time.timestamp()),
            "end": int(end_time.timestamp()),
            "currency": self.currency,
            "limit": min(limit, 100),
        }

        url = f"{self.base_url}/transactions"

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 401:
                    logger.error("Whale Alert API authentication failed")
                    return []

                if response.status != 200:
                    logger.error(f"Whale Alert API error: {response.status}")
                    return []

                data = await response.json()

                if data.get("result") != "success":
                    logger.error(f"Whale Alert API error: {data.get('message')}")
                    return []

                transactions = [
                    self._parse_transaction(tx) for tx in data.get("transactions", [])
                ]
                logger.info(f"Collected {len(transactions)} whale transactions")
                return transactions

        except aiohttp.ClientError as e:
            logger.error(f"Whale Alert API request failed: {e}")
            return []

    def _parse_transaction(self, data: dict[str, Any]) -> WhaleTransaction:
        """Parse raw transaction data into WhaleTransaction object.

        Data format from Whale Alert:
        {
            "blockchain": "bitcoin",
            "symbol": "BTC",
            "id": "xxx",
            "transaction_type": "transfer",
            "hash": "abc123...",
            "from": {"owner_type": "exchange", "owner": "binance"},
            "to": {"owner_type": "unknown", "owner": ""},
            "timestamp": 1234567890,
            "amount": 100.5,
            "amount_usd": 5000000,
            ...
        }
        """
        from_data = data.get("from", {})
        to_data = data.get("to", {})

        from_owner = from_data.get("owner") or from_data.get("owner_type")
        to_owner = to_data.get("owner") or to_data.get("owner_type")

        return WhaleTransaction(
            tx_hash=data.get("hash", data.get("id", "")),
            amount_usd=float(data.get("amount_usd", 0)),
            from_owner=from_owner if from_owner else None,
            to_owner=to_owner if to_owner else None,
            transaction_type=data.get("transaction_type", "unknown"),
            timestamp=datetime.fromtimestamp(data["timestamp"], tz=timezone.utc),
        )

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
