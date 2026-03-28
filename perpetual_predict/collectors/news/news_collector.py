"""News collector using RSS feeds."""

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.news.rss_collector import RSSCollector
from perpetual_predict.storage.models import NewsArticle
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class NewsCollector(BaseCollector):
    """Collects crypto news from RSS feeds (CoinTelegraph, CoinDesk)."""

    def __init__(self, rss_feed_urls: list[str] | None = None, **kwargs) -> None:
        self._rss = RSSCollector(feed_urls=rss_feed_urls)

    @property
    def used_fallback(self) -> bool:
        """Kept for backward compat. Always False since RSS is primary."""
        return False

    async def collect(self, **kwargs) -> list[NewsArticle]:
        try:
            articles = await self._rss.collect()
            logger.info(f"Collected {len(articles)} articles from RSS")
            return articles
        except Exception as e:
            logger.error(f"RSS collection failed: {e}")
            return []

    async def close(self) -> None:
        await self._rss.close()
