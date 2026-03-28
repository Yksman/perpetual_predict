"""Tests for NewsArticle data model."""

from datetime import datetime, timezone

from perpetual_predict.storage.models import NewsArticle

SAMPLE_TS = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
SAMPLE_COLLECTED = datetime(2026, 3, 28, 12, 5, 0, tzinfo=timezone.utc)


def test_create_with_votes():
    """Create NewsArticle with all fields including votes, assert values."""
    article = NewsArticle(
        timestamp=SAMPLE_TS,
        title="Bitcoin hits new high",
        source="CoinDesk",
        url="https://coindesk.com/article/1",
        votes_positive=42,
        votes_negative=3,
        votes_important=10,
        collected_at=SAMPLE_COLLECTED,
        collector_source="cryptopanic",
    )
    assert article.timestamp == SAMPLE_TS
    assert article.title == "Bitcoin hits new high"
    assert article.source == "CoinDesk"
    assert article.url == "https://coindesk.com/article/1"
    assert article.votes_positive == 42
    assert article.votes_negative == 3
    assert article.votes_important == 10
    assert article.collected_at == SAMPLE_COLLECTED
    assert article.collector_source == "cryptopanic"


def test_create_rss_without_votes():
    """Create with None votes and collector_source='rss'."""
    article = NewsArticle(
        timestamp=SAMPLE_TS,
        title="ETH upgrade news",
        source="CoinTelegraph",
        url="https://cointelegraph.com/article/2",
        votes_positive=None,
        votes_negative=None,
        votes_important=None,
        collected_at=SAMPLE_COLLECTED,
        collector_source="rss",
    )
    assert article.votes_positive is None
    assert article.votes_negative is None
    assert article.votes_important is None
    assert article.collector_source == "rss"


def test_to_dict():
    """Verify to_dict() returns correct dict with ISO timestamp strings."""
    article = NewsArticle(
        timestamp=SAMPLE_TS,
        title="Bitcoin hits new high",
        source="CoinDesk",
        url="https://coindesk.com/article/1",
        votes_positive=42,
        votes_negative=3,
        votes_important=10,
        collected_at=SAMPLE_COLLECTED,
        collector_source="cryptopanic",
    )
    d = article.to_dict()
    assert d["timestamp"] == SAMPLE_TS.isoformat()
    assert d["title"] == "Bitcoin hits new high"
    assert d["source"] == "CoinDesk"
    assert d["url"] == "https://coindesk.com/article/1"
    assert d["votes_positive"] == 42
    assert d["votes_negative"] == 3
    assert d["votes_important"] == 10
    assert d["collected_at"] == SAMPLE_COLLECTED.isoformat()
    assert d["collector_source"] == "cryptopanic"


def test_from_dict():
    """Verify from_dict() reconstructs from dict correctly."""
    d = {
        "timestamp": SAMPLE_TS.isoformat(),
        "title": "Bitcoin hits new high",
        "source": "CoinDesk",
        "url": "https://coindesk.com/article/1",
        "votes_positive": 42,
        "votes_negative": 3,
        "votes_important": 10,
        "collected_at": SAMPLE_COLLECTED.isoformat(),
        "collector_source": "cryptopanic",
    }
    article = NewsArticle.from_dict(d)
    assert article.timestamp == SAMPLE_TS
    assert article.title == "Bitcoin hits new high"
    assert article.source == "CoinDesk"
    assert article.url == "https://coindesk.com/article/1"
    assert article.votes_positive == 42
    assert article.votes_negative == 3
    assert article.votes_important == 10
    assert article.collected_at == SAMPLE_COLLECTED
    assert article.collector_source == "cryptopanic"


def test_from_dict_null_votes():
    """Verify from_dict handles None votes."""
    d = {
        "timestamp": SAMPLE_TS.isoformat(),
        "title": "RSS article",
        "source": "CoinTelegraph",
        "url": "https://cointelegraph.com/article/3",
        "votes_positive": None,
        "votes_negative": None,
        "votes_important": None,
        "collected_at": SAMPLE_COLLECTED.isoformat(),
        "collector_source": "rss",
    }
    article = NewsArticle.from_dict(d)
    assert article.votes_positive is None
    assert article.votes_negative is None
    assert article.votes_important is None
    assert article.collector_source == "rss"


def test_roundtrip():
    """Verify to_dict() → from_dict() roundtrip preserves data."""
    original = NewsArticle(
        timestamp=SAMPLE_TS,
        title="Roundtrip test article",
        source="CryptoNews",
        url="https://cryptonews.com/article/99",
        votes_positive=7,
        votes_negative=1,
        votes_important=2,
        collected_at=SAMPLE_COLLECTED,
        collector_source="cryptopanic",
    )
    restored = NewsArticle.from_dict(original.to_dict())
    assert restored.timestamp == original.timestamp
    assert restored.title == original.title
    assert restored.source == original.source
    assert restored.url == original.url
    assert restored.votes_positive == original.votes_positive
    assert restored.votes_negative == original.votes_negative
    assert restored.votes_important == original.votes_important
    assert restored.collected_at == original.collected_at
    assert restored.collector_source == original.collector_source
