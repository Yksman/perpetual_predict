"""Tests for RSSCollector."""

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_feed(entries=None, bozo=False):
    """Build a mock feedparser feed object."""
    feed = MagicMock()
    feed.bozo = bozo
    feed.entries = entries or []
    return feed


def _make_mock_entry(title="Test Title", link="https://example.com/article"):
    """Build a mock feedparser entry."""
    entry = MagicMock()
    entry.title = title
    entry.link = link
    entry.published_parsed = (2026, 3, 28, 8, 0, 0, 0, 0, 0)
    return entry


@pytest.mark.asyncio
async def test_collect_parses_entries():
    """Collector returns correctly parsed NewsArticle objects from feed entries."""
    from perpetual_predict.collectors.news.rss_collector import RSSCollector

    entry1 = _make_mock_entry(
        title="Bitcoin hits new high", link="https://cointelegraph.com/btc-high"
    )
    entry2 = _make_mock_entry(
        title="ETH 2.0 update released", link="https://coindesk.com/eth-update"
    )
    mock_feed = _make_mock_feed(entries=[entry1, entry2], bozo=False)

    with patch(
        "perpetual_predict.collectors.news.rss_collector.feedparser"
    ) as mock_feedparser:
        mock_feedparser.parse.return_value = mock_feed

        collector = RSSCollector(feed_urls=["https://cointelegraph.com/rss"])
        articles = await collector.collect()

    assert len(articles) == 2

    first = articles[0]
    assert first.title == "Bitcoin hits new high"
    assert first.url == "https://cointelegraph.com/btc-high"
    assert first.collector_source == "rss"
    assert first.votes_positive is None
    assert first.votes_negative is None
    assert first.votes_important is None
    assert first.timestamp.year == 2026
    assert first.timestamp.month == 3
    assert first.timestamp.day == 28

    second = articles[1]
    assert second.title == "ETH 2.0 update released"
    assert second.collector_source == "rss"
    assert second.votes_positive is None


@pytest.mark.asyncio
async def test_collect_empty_feed():
    """Collector returns empty list when feed has no entries."""
    from perpetual_predict.collectors.news.rss_collector import RSSCollector

    mock_feed = _make_mock_feed(entries=[], bozo=False)

    with patch(
        "perpetual_predict.collectors.news.rss_collector.feedparser"
    ) as mock_feedparser:
        mock_feedparser.parse.return_value = mock_feed

        collector = RSSCollector(feed_urls=["https://cointelegraph.com/rss"])
        articles = await collector.collect()

    assert articles == []


@pytest.mark.asyncio
async def test_collect_malformed_feed_continues():
    """Collector returns empty list and does not crash on malformed (bozo) feed."""
    from perpetual_predict.collectors.news.rss_collector import RSSCollector

    mock_feed = _make_mock_feed(entries=[], bozo=True)

    with patch(
        "perpetual_predict.collectors.news.rss_collector.feedparser"
    ) as mock_feedparser:
        mock_feedparser.parse.return_value = mock_feed

        collector = RSSCollector(feed_urls=["https://cointelegraph.com/rss"])
        articles = await collector.collect()

    assert articles == []
