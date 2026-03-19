"""CryptoPanic API collector for cryptocurrency news."""

from datetime import datetime, timezone
from typing import Any

import aiohttp

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.config import get_settings
from perpetual_predict.storage.models import NewsItem
from perpetual_predict.utils import get_logger

logger = get_logger(__name__)


class CryptoPanicCollector(BaseCollector):
    """Collector for cryptocurrency news from CryptoPanic API.

    CryptoPanic aggregates news from various crypto news sources
    and provides sentiment analysis.
    """

    def __init__(
        self,
        api_key: str | None = None,
        currencies: str | None = None,
    ):
        """Initialize CryptoPanic collector.

        Args:
            api_key: CryptoPanic API key. If None, uses settings.
            currencies: Comma-separated currency codes (e.g., "BTC,ETH").
        """
        settings = get_settings()
        cp_config = settings.cryptopanic

        self.api_key = api_key or cp_config.api_key
        self.base_url = cp_config.base_url
        self.currencies = currencies or cp_config.filter_currencies

        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def collect(
        self,
        filter_kind: str | None = None,
        public: bool = True,
        limit: int = 50,
        **kwargs: Any,
    ) -> list[NewsItem]:
        """Collect news items.

        Args:
            filter_kind: Filter type ("rising", "hot", "bullish", "bearish", "lol").
            public: Whether to fetch public posts only.
            limit: Maximum number of items to collect.
            **kwargs: Additional arguments (ignored).

        Returns:
            List of NewsItem objects.
        """
        if not self.api_key:
            logger.warning("CryptoPanic API key not configured, skipping collection")
            return []

        logger.info(
            f"Collecting news for currencies: {self.currencies}, "
            f"filter={filter_kind or 'all'}"
        )

        params: dict[str, Any] = {
            "auth_token": self.api_key,
            "currencies": self.currencies,
            "public": "true" if public else "false",
        }

        if filter_kind:
            params["filter"] = filter_kind

        url = f"{self.base_url}/posts/"

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 401:
                    logger.error("CryptoPanic API authentication failed")
                    return []

                if response.status != 200:
                    logger.error(f"CryptoPanic API error: {response.status}")
                    return []

                data = await response.json()

                results = data.get("results", [])[:limit]
                news_items = [self._parse_news(item) for item in results]

                logger.info(f"Collected {len(news_items)} news items")
                return news_items

        except aiohttp.ClientError as e:
            logger.error(f"CryptoPanic API request failed: {e}")
            return []

    def _parse_news(self, data: dict[str, Any]) -> NewsItem:
        """Parse raw news data into NewsItem object.

        Data format from CryptoPanic:
        {
            "kind": "news",
            "domain": "coindesk.com",
            "source": {"title": "CoinDesk", "region": "en", ...},
            "title": "Bitcoin Hits New High...",
            "published_at": "2024-01-15T10:30:00Z",
            "slug": "bitcoin-hits-new-high",
            "currencies": [{"code": "BTC", ...}],
            "id": 123456,
            "url": "https://cryptopanic.com/news/...",
            "votes": {"negative": 0, "positive": 5, "saved": 10, ...},
            ...
        }
        """
        # Determine sentiment from votes if available
        votes = data.get("votes", {})
        positive = votes.get("positive", 0)
        negative = votes.get("negative", 0)

        sentiment = None
        if positive > 0 or negative > 0:
            if positive > negative * 2:
                sentiment = "bullish"
            elif negative > positive * 2:
                sentiment = "bearish"
            else:
                sentiment = "neutral"

        # Parse published_at
        published_str = data.get("published_at", "")
        if published_str:
            # Handle ISO format with Z suffix
            published_str = published_str.replace("Z", "+00:00")
            published_at = datetime.fromisoformat(published_str)
        else:
            published_at = datetime.now(timezone.utc)

        return NewsItem(
            url=data.get("url", ""),
            title=data.get("title", ""),
            sentiment=sentiment,
            published_at=published_at,
        )

    async def collect_by_sentiment(self, sentiment: str, limit: int = 20) -> list[NewsItem]:
        """Collect news items filtered by sentiment.

        Args:
            sentiment: Sentiment filter ("bullish" or "bearish").
            limit: Maximum number of items.

        Returns:
            List of NewsItem objects matching the sentiment.
        """
        if sentiment not in ("bullish", "bearish"):
            logger.warning(f"Invalid sentiment filter: {sentiment}")
            return []

        return await self.collect(filter_kind=sentiment, limit=limit)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
