"""CryptoPanic API news collector."""

from datetime import datetime, timezone

import aiohttp

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.storage.models import NewsArticle
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

CRYPTOPANIC_API_URL = "https://cryptopanic.com/api/v1/posts/"


class CryptoPanicCollector(BaseCollector):
    """Collector for crypto news from CryptoPanic API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize CryptoPanic collector.

        Args:
            api_key: CryptoPanic API authentication token.
            session: Optional aiohttp session. If not provided, one will be created.
        """
        self._api_key = api_key
        self._session = session
        self._owns_session = session is None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def collect(self, **kwargs) -> list[NewsArticle]:
        """Collect news articles from CryptoPanic.

        Returns:
            List of NewsArticle objects.
        """
        params = {"auth_token": self._api_key, "kind": "news", "public": "true"}

        async with self.session.get(CRYPTOPANIC_API_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        articles = []
        for item in data.get("results", []):
            articles.append(self._parse_article(item))

        logger.debug(f"Collected {len(articles)} articles from CryptoPanic")
        return articles

    def _parse_article(self, data: dict) -> NewsArticle:
        """Parse a single article dict into a NewsArticle.

        Args:
            data: Raw article dict from API response.

        Returns:
            NewsArticle object.
        """
        published = data.get("published_at", "")
        if published:
            timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(timezone.utc)

        votes = data.get("votes", {})

        return NewsArticle(
            timestamp=timestamp,
            title=data.get("title", ""),
            source=data.get("source", {}).get("title", "Unknown"),
            url=data.get("url", ""),
            votes_positive=votes.get("positive", 0),
            votes_negative=votes.get("negative", 0),
            votes_important=votes.get("important", 0),
            collected_at=datetime.now(timezone.utc),
            collector_source="cryptopanic",
        )

    async def close(self) -> None:
        """Close the session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
