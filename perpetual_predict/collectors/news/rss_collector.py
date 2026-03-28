"""RSS feed news collector (fallback for CryptoPanic)."""

import asyncio
from calendar import timegm
from datetime import datetime, timezone

import feedparser

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.storage.models import NewsArticle
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
]


class RSSCollector(BaseCollector):
    """Collector for crypto news via RSS feeds. No API key required."""

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        self._feed_urls = feed_urls or DEFAULT_RSS_FEEDS

    async def collect(self, **kwargs) -> list[NewsArticle]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._collect_sync)

    def _collect_sync(self) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        for feed_url in self._feed_urls:
            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo:
                    logger.warning(f"Malformed RSS feed: {feed_url}")
                    continue
                for entry in feed.entries:
                    article = self._parse_entry(entry, feed_url)
                    if article:
                        articles.append(article)
                logger.debug(f"Collected {len(feed.entries)} entries from {feed_url}")
            except Exception as e:
                logger.warning(f"Failed to parse RSS feed {feed_url}: {e}")
                continue
        logger.info(f"Collected {len(articles)} articles from RSS feeds")
        return articles

    def _parse_entry(self, entry: object, feed_url: str) -> NewsArticle | None:
        title = getattr(entry, "title", None)
        link = getattr(entry, "link", None)
        if not title or not link:
            return None

        published_parsed = getattr(entry, "published_parsed", None)
        if published_parsed:
            timestamp = datetime.fromtimestamp(timegm(published_parsed), tz=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        source = self._extract_source_name(feed_url)
        return NewsArticle(
            timestamp=timestamp,
            title=title,
            source=source,
            url=link,
            votes_positive=None,
            votes_negative=None,
            votes_important=None,
            collected_at=datetime.now(timezone.utc),
            collector_source="rss",
        )

    def _extract_source_name(self, feed_url: str) -> str:
        if "cointelegraph" in feed_url:
            return "CoinTelegraph"
        if "coindesk" in feed_url:
            return "CoinDesk"
        from urllib.parse import urlparse

        return urlparse(feed_url).netloc

    async def close(self) -> None:
        pass
