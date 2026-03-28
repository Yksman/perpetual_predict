"""News collector orchestrator with CryptoPanic primary and RSS fallback."""
from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.news.cryptopanic_collector import CryptoPanicCollector
from perpetual_predict.collectors.news.rss_collector import RSSCollector
from perpetual_predict.storage.models import NewsArticle
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class NewsCollector(BaseCollector):
    """Orchestrator: CryptoPanic (primary) → RSS (fallback)."""

    def __init__(self, cryptopanic_api_key: str = "", rss_feed_urls: list[str] | None = None) -> None:
        self._cryptopanic = CryptoPanicCollector(api_key=cryptopanic_api_key) if cryptopanic_api_key else None
        self._rss = RSSCollector(feed_urls=rss_feed_urls)
        self._used_fallback = False

    @property
    def used_fallback(self) -> bool:
        return self._used_fallback

    async def collect(self, **kwargs) -> list[NewsArticle]:
        self._used_fallback = False
        if self._cryptopanic:
            try:
                articles = await self._cryptopanic.collect()
                logger.info(f"Collected {len(articles)} articles from CryptoPanic")
                return articles
            except Exception as e:
                logger.warning(f"CryptoPanic failed, falling back to RSS: {e}")
        self._used_fallback = True
        try:
            articles = await self._rss.collect()
            logger.info(f"Collected {len(articles)} articles from RSS (fallback)")
            return articles
        except Exception as e:
            logger.error(f"RSS fallback also failed: {e}")
            return []

    async def close(self) -> None:
        if self._cryptopanic:
            await self._cryptopanic.close()
        await self._rss.close()
