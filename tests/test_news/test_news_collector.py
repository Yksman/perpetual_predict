"""Tests for NewsCollector (RSS-based)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from perpetual_predict.collectors.news.news_collector import NewsCollector
from perpetual_predict.storage.models import NewsArticle


def _make_article(title):
    return NewsArticle(
        timestamp=datetime.now(timezone.utc),
        title=title,
        source="TestSource",
        url=f"https://example.com/{title.replace(' ', '-')}",
        votes_positive=None,
        votes_negative=None,
        votes_important=None,
        collected_at=datetime.now(timezone.utc),
        collector_source="rss",
    )


@pytest.mark.asyncio
async def test_collect_returns_articles():
    articles = [_make_article("BTC News"), _make_article("ETH Update")]
    collector = NewsCollector()
    collector._rss = AsyncMock()
    collector._rss.collect = AsyncMock(return_value=articles)

    result = await collector.collect()

    assert len(result) == 2
    assert result[0].title == "BTC News"
    collector._rss.collect.assert_called_once()


@pytest.mark.asyncio
async def test_collect_returns_empty_on_failure():
    collector = NewsCollector()
    collector._rss = AsyncMock()
    collector._rss.collect = AsyncMock(side_effect=Exception("RSS down"))

    result = await collector.collect()

    assert result == []


@pytest.mark.asyncio
async def test_used_fallback_always_false():
    collector = NewsCollector()
    assert collector.used_fallback is False
