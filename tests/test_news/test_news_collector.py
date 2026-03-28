"""Tests for NewsCollector orchestrator."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from perpetual_predict.collectors.news.news_collector import NewsCollector
from perpetual_predict.storage.models import NewsArticle


def _make_article(title, source="cryptopanic"):
    return NewsArticle(
        timestamp=datetime.now(timezone.utc),
        title=title,
        source="TestSource",
        url=f"https://example.com/{title.replace(' ', '-')}",
        votes_positive=10 if source == "cryptopanic" else None,
        votes_negative=2 if source == "cryptopanic" else None,
        votes_important=5 if source == "cryptopanic" else None,
        collected_at=datetime.now(timezone.utc),
        collector_source=source,
    )


@pytest.mark.asyncio
async def test_uses_cryptopanic_when_available():
    """CryptoPanic is used when available and returns articles; RSS is not called."""
    article = _make_article("BTC Moon", source="cryptopanic")
    collector = NewsCollector(cryptopanic_api_key="test-key")
    collector._cryptopanic = AsyncMock()
    collector._cryptopanic.collect = AsyncMock(return_value=[article])
    collector._rss = AsyncMock()
    collector._rss.collect = AsyncMock(return_value=[])

    result = await collector.collect()

    assert result == [article]
    collector._cryptopanic.collect.assert_called_once()
    collector._rss.collect.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_rss_on_cryptopanic_failure():
    """RSS fallback is used when CryptoPanic raises an exception."""
    rss_article = _make_article("ETH Update", source="rss")
    collector = NewsCollector(cryptopanic_api_key="test-key")
    collector._cryptopanic = AsyncMock()
    collector._cryptopanic.collect = AsyncMock(side_effect=Exception("API error"))
    collector._rss = AsyncMock()
    collector._rss.collect = AsyncMock(return_value=[rss_article])

    result = await collector.collect()

    assert result == [rss_article]
    collector._cryptopanic.collect.assert_called_once()
    collector._rss.collect.assert_called_once()
    assert collector.used_fallback is True


@pytest.mark.asyncio
async def test_uses_rss_when_no_api_key():
    """RSS is used directly when no CryptoPanic API key is provided."""
    rss_article = _make_article("Crypto News", source="rss")
    collector = NewsCollector(cryptopanic_api_key="")
    collector._rss = AsyncMock()
    collector._rss.collect = AsyncMock(return_value=[rss_article])

    result = await collector.collect()

    assert result == [rss_article]
    assert collector._cryptopanic is None
    collector._rss.collect.assert_called_once()
    assert collector.used_fallback is True


@pytest.mark.asyncio
async def test_returns_empty_when_both_fail():
    """Empty list is returned without crash when both sources fail."""
    collector = NewsCollector(cryptopanic_api_key="test-key")
    collector._cryptopanic = AsyncMock()
    collector._cryptopanic.collect = AsyncMock(side_effect=Exception("CryptoPanic down"))
    collector._rss = AsyncMock()
    collector._rss.collect = AsyncMock(side_effect=Exception("RSS down"))

    result = await collector.collect()

    assert result == []
    assert collector.used_fallback is True
