"""Fear & Greed Index collector from Alternative.me API."""

from datetime import datetime, timezone

import aiohttp

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.storage.models import FearGreedIndex
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

FEAR_GREED_API_URL = "https://api.alternative.me/fng/"


class FearGreedCollector(BaseCollector):
    """Collector for Fear & Greed Index from Alternative.me."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize Fear & Greed Index collector.

        Args:
            session: Optional aiohttp session. If not provided, one will be created.
        """
        self._session = session
        self._owns_session = session is None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def collect(self, limit: int = 1) -> list[FearGreedIndex]:
        """Collect Fear & Greed Index data.

        Args:
            limit: Number of records to fetch (default 1 for current).

        Returns:
            List of FearGreedIndex objects.
        """
        params = {"limit": limit, "format": "json"}

        async with self.session.get(FEAR_GREED_API_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        results: list[FearGreedIndex] = []
        for item in data.get("data", []):
            fgi = self._parse_fear_greed(item)
            results.append(fgi)

        logger.debug(f"Collected {len(results)} Fear & Greed Index records")
        return results

    async def collect_current(self) -> FearGreedIndex | None:
        """Collect current Fear & Greed Index value.

        Returns:
            Current FearGreedIndex or None if unavailable.
        """
        results = await self.collect(limit=1)
        return results[0] if results else None

    def _parse_fear_greed(self, data: dict) -> FearGreedIndex:
        """Parse API response into FearGreedIndex object.

        Args:
            data: Raw data from API.

        Returns:
            FearGreedIndex object.
        """
        timestamp = datetime.fromtimestamp(
            int(data["timestamp"]), tz=timezone.utc
        )

        return FearGreedIndex(
            timestamp=timestamp,
            value=int(data["value"]),
            classification=data["value_classification"],
        )

    async def close(self) -> None:
        """Close the session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
