"""Tests for news articles database CRUD operations."""

from datetime import datetime, timedelta, timezone

import pytest

from perpetual_predict.storage.database import get_database
from perpetual_predict.storage.models import NewsArticle

SAMPLE_TS = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
SAMPLE_COLLECTED = datetime(2026, 3, 28, 12, 5, 0, tzinfo=timezone.utc)


def _make_article(
    *,
    title: str = "Bitcoin hits new high",
    source: str = "CoinDesk",
    url: str = "https://coindesk.com/article/1",
    timestamp: datetime = SAMPLE_TS,
    votes_positive: int | None = 42,
    votes_negative: int | None = 3,
    votes_important: int | None = 10,
    collected_at: datetime = SAMPLE_COLLECTED,
    collector_source: str = "cryptopanic",
) -> NewsArticle:
    return NewsArticle(
        timestamp=timestamp,
        title=title,
        source=source,
        url=url,
        votes_positive=votes_positive,
        votes_negative=votes_negative,
        votes_important=votes_important,
        collected_at=collected_at,
        collector_source=collector_source,
    )


@pytest.fixture
async def db(tmp_path):
    db_path = tmp_path / "test.db"
    async with get_database(str(db_path)) as database:
        yield database


@pytest.mark.asyncio
async def test_insert_and_get(db):
    """Insert one article, get_recent_news(hours=4), verify fields."""
    article = _make_article()
    await db.insert_news_articles([article])

    results = await db.get_recent_news(hours=4)
    assert len(results) == 1

    got = results[0]
    assert got.title == "Bitcoin hits new high"
    assert got.source == "CoinDesk"
    assert got.url == "https://coindesk.com/article/1"
    assert got.votes_positive == 42
    assert got.votes_negative == 3
    assert got.votes_important == 10
    assert got.collector_source == "cryptopanic"


@pytest.mark.asyncio
async def test_insert_duplicate_url_replaces(db):
    """Insert same URL twice with different title, verify UPDATE behavior."""
    article1 = _make_article(title="Original title")
    article2 = _make_article(title="Updated title")

    await db.insert_news_articles([article1])
    await db.insert_news_articles([article2])

    results = await db.get_recent_news(hours=4)
    assert len(results) == 1
    assert results[0].title == "Updated title"


@pytest.mark.asyncio
async def test_get_recent_filters_by_time(db):
    """Insert recent + old articles, verify 4H filter excludes old ones."""
    now = datetime.now(timezone.utc)
    recent = _make_article(
        url="https://example.com/recent",
        timestamp=now - timedelta(hours=1),
    )
    old = _make_article(
        url="https://example.com/old",
        timestamp=now - timedelta(hours=10),
    )
    await db.insert_news_articles([recent, old])

    results = await db.get_recent_news(hours=4)
    assert len(results) == 1
    assert results[0].url == "https://example.com/recent"


@pytest.mark.asyncio
async def test_get_recent_orders_by_timestamp_desc(db):
    """Insert 3 articles, verify order is newest-first."""
    now = datetime.now(timezone.utc)
    articles = [
        _make_article(
            url=f"https://example.com/{i}",
            title=f"Article {i}",
            timestamp=now - timedelta(hours=i),
        )
        for i in range(3)
    ]
    await db.insert_news_articles(articles)

    results = await db.get_recent_news(hours=4)
    assert len(results) == 3
    assert results[0].title == "Article 0"  # most recent
    assert results[1].title == "Article 1"
    assert results[2].title == "Article 2"  # oldest


@pytest.mark.asyncio
async def test_get_recent_respects_limit(db):
    """Insert 10 articles, limit=5, verify count."""
    now = datetime.now(timezone.utc)
    articles = [
        _make_article(
            url=f"https://example.com/{i}",
            title=f"Article {i}",
            timestamp=now - timedelta(minutes=i),
        )
        for i in range(10)
    ]
    await db.insert_news_articles(articles)

    results = await db.get_recent_news(hours=4, limit=5)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_insert_rss_article_with_null_votes(db):
    """Insert RSS article with None votes, verify stored as NULL."""
    article = _make_article(
        votes_positive=None,
        votes_negative=None,
        votes_important=None,
        collector_source="rss",
    )
    await db.insert_news_articles([article])

    results = await db.get_recent_news(hours=4)
    assert len(results) == 1
    assert results[0].votes_positive is None
    assert results[0].votes_negative is None
    assert results[0].votes_important is None
    assert results[0].collector_source == "rss"


@pytest.mark.asyncio
async def test_insert_empty_list(db):
    """Insert empty list, verify no error and no rows."""
    await db.insert_news_articles([])

    results = await db.get_recent_news(hours=4)
    assert len(results) == 0
