# News/Event Sentiment Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CryptoPanic API (primary) + RSS fallback news collection as a new seed data module for the LLM prediction agent.

**Architecture:** NewsCollector orchestrator calls CryptoPanicCollector first, falls back to RSSCollector on failure. Collected articles are stored in SQLite, queried at prediction time, and formatted into the prompt as a `news` module. Registered in EXPERIMENTAL_MODULES for A/B testing.

**Tech Stack:** aiohttp (CryptoPanic API), feedparser (RSS parsing), aiosqlite (storage), existing BaseCollector pattern

**Spec:** `docs/superpowers/specs/2026-03-28-news-sentiment-module-design.md`

---

### Task 1: Add feedparser dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add feedparser to dependencies**

In `pyproject.toml`, add `feedparser` to the dependencies list:

```toml
    "feedparser>=6.0.0",
```

Add it after the existing `aiohttp>=3.9.0` line.

- [ ] **Step 2: Install**

Run: `uv sync`
Expected: feedparser installed successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add feedparser dependency for RSS news collection"
```

---

### Task 2: NewsArticle data model

**Files:**
- Modify: `perpetual_predict/storage/models.py` (insert after line 222, before `class Prediction`)
- Create: `tests/test_news/__init__.py`
- Create: `tests/test_news/test_news_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_news/__init__.py` (empty file).

Create `tests/test_news/test_news_models.py`:

```python
"""Tests for NewsArticle data model."""

from datetime import datetime, timezone

from perpetual_predict.storage.models import NewsArticle


class TestNewsArticle:
    """Tests for NewsArticle dataclass."""

    def test_create_with_votes(self):
        article = NewsArticle(
            timestamp=datetime(2026, 3, 28, 8, 0, tzinfo=timezone.utc),
            title="Bitcoin ETF sees record inflow",
            source="CoinDesk",
            url="https://coindesk.com/article/1",
            votes_positive=18,
            votes_negative=2,
            votes_important=5,
            collected_at=datetime(2026, 3, 28, 8, 1, tzinfo=timezone.utc),
            collector_source="cryptopanic",
        )
        assert article.title == "Bitcoin ETF sees record inflow"
        assert article.votes_positive == 18
        assert article.collector_source == "cryptopanic"

    def test_create_rss_without_votes(self):
        article = NewsArticle(
            timestamp=datetime(2026, 3, 28, 7, 0, tzinfo=timezone.utc),
            title="Fed signals rate pause",
            source="CoinTelegraph",
            url="https://cointelegraph.com/article/1",
            votes_positive=None,
            votes_negative=None,
            votes_important=None,
            collected_at=datetime(2026, 3, 28, 8, 1, tzinfo=timezone.utc),
            collector_source="rss",
        )
        assert article.votes_positive is None
        assert article.collector_source == "rss"

    def test_to_dict(self):
        article = NewsArticle(
            timestamp=datetime(2026, 3, 28, 8, 0, tzinfo=timezone.utc),
            title="Test headline",
            source="TestSource",
            url="https://example.com/1",
            votes_positive=10,
            votes_negative=3,
            votes_important=5,
            collected_at=datetime(2026, 3, 28, 8, 1, tzinfo=timezone.utc),
            collector_source="cryptopanic",
        )
        d = article.to_dict()
        assert d["title"] == "Test headline"
        assert d["source"] == "TestSource"
        assert d["votes_positive"] == 10
        assert d["collector_source"] == "cryptopanic"
        assert isinstance(d["timestamp"], str)

    def test_from_dict(self):
        data = {
            "timestamp": "2026-03-28T08:00:00+00:00",
            "title": "Test headline",
            "source": "TestSource",
            "url": "https://example.com/1",
            "votes_positive": 10,
            "votes_negative": 3,
            "votes_important": 5,
            "collected_at": "2026-03-28T08:01:00+00:00",
            "collector_source": "cryptopanic",
        }
        article = NewsArticle.from_dict(data)
        assert article.title == "Test headline"
        assert article.votes_positive == 10
        assert article.timestamp.year == 2026

    def test_from_dict_null_votes(self):
        data = {
            "timestamp": "2026-03-28T07:00:00+00:00",
            "title": "RSS headline",
            "source": "CoinTelegraph",
            "url": "https://cointelegraph.com/1",
            "votes_positive": None,
            "votes_negative": None,
            "votes_important": None,
            "collected_at": "2026-03-28T08:01:00+00:00",
            "collector_source": "rss",
        }
        article = NewsArticle.from_dict(data)
        assert article.votes_positive is None
        assert article.collector_source == "rss"

    def test_roundtrip(self):
        original = NewsArticle(
            timestamp=datetime(2026, 3, 28, 8, 0, tzinfo=timezone.utc),
            title="Roundtrip test",
            source="TestSource",
            url="https://example.com/roundtrip",
            votes_positive=5,
            votes_negative=1,
            votes_important=3,
            collected_at=datetime(2026, 3, 28, 8, 1, tzinfo=timezone.utc),
            collector_source="cryptopanic",
        )
        restored = NewsArticle.from_dict(original.to_dict())
        assert restored.title == original.title
        assert restored.url == original.url
        assert restored.votes_positive == original.votes_positive
        assert restored.collector_source == original.collector_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_news/test_news_models.py -v`
Expected: ImportError — `cannot import name 'NewsArticle' from 'perpetual_predict.storage.models'`

- [ ] **Step 3: Write the implementation**

In `perpetual_predict/storage/models.py`, insert after the `MacroIndicator` class (after line 222) and before `class Prediction` (line 225):

```python
@dataclass
class NewsArticle:
    """News article collected from CryptoPanic or RSS feeds."""

    timestamp: datetime  # Article publish time
    title: str
    source: str  # "CoinDesk", "CoinTelegraph", etc.
    url: str
    votes_positive: int | None = None  # CryptoPanic votes (None for RSS)
    votes_negative: int | None = None
    votes_important: int | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    collector_source: str = "cryptopanic"  # "cryptopanic" | "rss"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "votes_positive": self.votes_positive,
            "votes_negative": self.votes_negative,
            "votes_important": self.votes_important,
            "collected_at": self.collected_at.isoformat(),
            "collector_source": self.collector_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NewsArticle":
        """Create from dictionary (database row)."""
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        collected = data.get("collected_at", datetime.now(timezone.utc))
        if isinstance(collected, str):
            collected = datetime.fromisoformat(collected)
        return cls(
            timestamp=ts,
            title=data["title"],
            source=data["source"],
            url=data["url"],
            votes_positive=data.get("votes_positive"),
            votes_negative=data.get("votes_negative"),
            votes_important=data.get("votes_important"),
            collected_at=collected,
            collector_source=data.get("collector_source", "cryptopanic"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_news/test_news_models.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint check**

Run: `ruff check perpetual_predict/storage/models.py tests/test_news/`

- [ ] **Step 6: Commit**

```bash
git add perpetual_predict/storage/models.py tests/test_news/
git commit -m "feat: add NewsArticle data model for news collection"
```

---

### Task 3: Database table and CRUD operations

**Files:**
- Modify: `perpetual_predict/storage/database.py`
- Create: `tests/test_news/test_news_database.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_news/test_news_database.py`:

```python
"""Tests for news article database operations."""

import pytest
from datetime import datetime, timedelta, timezone

from perpetual_predict.storage.database import get_database
from perpetual_predict.storage.models import NewsArticle


@pytest.fixture
async def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    async with get_database(str(db_path)) as database:
        yield database


def _make_article(
    title: str = "Test headline",
    hours_ago: float = 0,
    votes_positive: int | None = 10,
    collector_source: str = "cryptopanic",
) -> NewsArticle:
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return NewsArticle(
        timestamp=ts,
        title=title,
        source="TestSource",
        url=f"https://example.com/{title.replace(' ', '-')}-{hours_ago}",
        votes_positive=votes_positive,
        votes_negative=2 if votes_positive is not None else None,
        votes_important=3 if votes_positive is not None else None,
        collected_at=datetime.now(timezone.utc),
        collector_source=collector_source,
    )


class TestNewsDatabase:
    """Tests for news article database operations."""

    @pytest.mark.asyncio
    async def test_insert_and_get(self, db):
        article = _make_article("Bitcoin rallies")
        await db.insert_news_articles([article])
        results = await db.get_recent_news(hours=4)
        assert len(results) == 1
        assert results[0].title == "Bitcoin rallies"

    @pytest.mark.asyncio
    async def test_insert_duplicate_url_replaces(self, db):
        article1 = _make_article("Original title")
        article2 = NewsArticle(
            timestamp=article1.timestamp,
            title="Updated title",
            source="NewSource",
            url=article1.url,  # Same URL
            votes_positive=20,
            votes_negative=5,
            votes_important=10,
            collected_at=datetime.now(timezone.utc),
            collector_source="cryptopanic",
        )
        await db.insert_news_articles([article1])
        await db.insert_news_articles([article2])
        results = await db.get_recent_news(hours=4)
        assert len(results) == 1
        assert results[0].title == "Updated title"
        assert results[0].votes_positive == 20

    @pytest.mark.asyncio
    async def test_get_recent_filters_by_time(self, db):
        recent = _make_article("Recent news", hours_ago=1)
        old = _make_article("Old news", hours_ago=10)
        await db.insert_news_articles([recent, old])
        results = await db.get_recent_news(hours=4)
        assert len(results) == 1
        assert results[0].title == "Recent news"

    @pytest.mark.asyncio
    async def test_get_recent_orders_by_timestamp_desc(self, db):
        early = _make_article("Early", hours_ago=3)
        mid = _make_article("Mid", hours_ago=2)
        late = _make_article("Late", hours_ago=1)
        await db.insert_news_articles([early, mid, late])
        results = await db.get_recent_news(hours=4)
        assert results[0].title == "Late"
        assert results[1].title == "Mid"
        assert results[2].title == "Early"

    @pytest.mark.asyncio
    async def test_get_recent_respects_limit(self, db):
        articles = [_make_article(f"Article {i}", hours_ago=i * 0.5) for i in range(10)]
        await db.insert_news_articles(articles)
        results = await db.get_recent_news(hours=24, limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_insert_rss_article_with_null_votes(self, db):
        article = _make_article("RSS article", votes_positive=None, collector_source="rss")
        await db.insert_news_articles([article])
        results = await db.get_recent_news(hours=4)
        assert len(results) == 1
        assert results[0].votes_positive is None
        assert results[0].collector_source == "rss"

    @pytest.mark.asyncio
    async def test_insert_empty_list(self, db):
        await db.insert_news_articles([])
        results = await db.get_recent_news(hours=4)
        assert len(results) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_news/test_news_database.py -v`
Expected: AttributeError — `Database has no attribute 'insert_news_articles'`

- [ ] **Step 3: Add table creation SQL**

In `perpetual_predict/storage/database.py`, add after `CREATE_MACRO_INDICATORS_TABLE` (after line 208):

```python
CREATE_NEWS_ARTICLES_TABLE = """
CREATE TABLE IF NOT EXISTS news_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    votes_positive INTEGER,
    votes_negative INTEGER,
    votes_important INTEGER,
    collected_at TEXT NOT NULL,
    collector_source TEXT NOT NULL,
    UNIQUE(url)
)
"""
```

In the `connect()` method (around line 300), add table creation:

```python
await self._connection.execute(CREATE_NEWS_ARTICLES_TABLE)
```

Add after the `CREATE_MACRO_INDICATORS_TABLE` execute line.

Add index to `CREATE_INDEXES` list:

```python
"CREATE INDEX IF NOT EXISTS idx_news_articles_timestamp ON news_articles(timestamp DESC)",
```

- [ ] **Step 4: Add insert and query methods**

In `perpetual_predict/storage/database.py`, add after the macro indicator methods (after line 943):

```python
    # News article operations
    async def insert_news_articles(self, articles: list[NewsArticle]) -> None:
        """Insert multiple news articles (upsert by URL)."""
        if not articles:
            return
        sql = """
        INSERT OR REPLACE INTO news_articles
        (timestamp, title, source, url, votes_positive, votes_negative,
         votes_important, collected_at, collector_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = [
            (
                a.timestamp.isoformat(),
                a.title,
                a.source,
                a.url,
                a.votes_positive,
                a.votes_negative,
                a.votes_important,
                a.collected_at.isoformat(),
                a.collector_source,
            )
            for a in articles
        ]
        await self.connection.executemany(sql, data)
        await self.connection.commit()

    async def get_recent_news(
        self,
        hours: int = 4,
        limit: int | None = None,
    ) -> list[NewsArticle]:
        """Get news articles from the last N hours.

        Args:
            hours: Number of hours to look back.
            limit: Maximum number of articles to return.

        Returns:
            List of NewsArticle ordered by timestamp DESC.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        sql = "SELECT * FROM news_articles WHERE timestamp >= ? ORDER BY timestamp DESC"
        params: list[Any] = [cutoff]

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [NewsArticle.from_dict(dict(row)) for row in rows]
```

Add the necessary imports at the top of database.py if not already present:

```python
from perpetual_predict.storage.models import NewsArticle
```

(Check if `NewsArticle` needs to be added to the existing import line.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_news/test_news_database.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Lint check**

Run: `ruff check perpetual_predict/storage/database.py tests/test_news/test_news_database.py`

- [ ] **Step 7: Commit**

```bash
git add perpetual_predict/storage/database.py tests/test_news/test_news_database.py
git commit -m "feat: add news_articles table and CRUD operations"
```

---

### Task 4: CryptoPanic collector

**Files:**
- Create: `perpetual_predict/collectors/news/__init__.py`
- Create: `perpetual_predict/collectors/news/cryptopanic_collector.py`
- Create: `tests/test_news/test_cryptopanic_collector.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_news/test_cryptopanic_collector.py`:

```python
"""Tests for CryptoPanic collector."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from perpetual_predict.collectors.news.cryptopanic_collector import CryptoPanicCollector


SAMPLE_RESPONSE = {
    "results": [
        {
            "title": "Bitcoin ETF sees record inflow",
            "url": "https://example.com/btc-etf",
            "source": {"title": "CoinDesk", "domain": "coindesk.com"},
            "published_at": "2026-03-28T08:15:00Z",
            "currencies": [{"code": "BTC"}],
            "votes": {
                "positive": 18,
                "negative": 2,
                "important": 5,
                "liked": 10,
                "disliked": 1,
                "toxic": 0,
            },
        },
        {
            "title": "New DeFi protocol launches",
            "url": "https://example.com/defi",
            "source": {"title": "CryptoSlate", "domain": "cryptoslate.com"},
            "published_at": "2026-03-28T07:30:00Z",
            "currencies": [{"code": "ETH"}],
            "votes": {
                "positive": 5,
                "negative": 1,
                "important": 2,
                "liked": 3,
                "disliked": 0,
                "toxic": 0,
            },
        },
    ]
}


class TestCryptoPanicCollector:
    """Tests for CryptoPanicCollector."""

    @pytest.mark.asyncio
    async def test_collect_parses_articles(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_RESPONSE)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        collector = CryptoPanicCollector(api_key="test_key", session=mock_session)
        articles = await collector.collect()

        assert len(articles) == 2
        assert articles[0].title == "Bitcoin ETF sees record inflow"
        assert articles[0].source == "CoinDesk"
        assert articles[0].votes_positive == 18
        assert articles[0].votes_negative == 2
        assert articles[0].votes_important == 5
        assert articles[0].collector_source == "cryptopanic"

    @pytest.mark.asyncio
    async def test_collect_second_article(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_RESPONSE)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        collector = CryptoPanicCollector(api_key="test_key", session=mock_session)
        articles = await collector.collect()

        assert articles[1].title == "New DeFi protocol launches"
        assert articles[1].source == "CryptoSlate"

    @pytest.mark.asyncio
    async def test_collect_empty_response(self):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"results": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        collector = CryptoPanicCollector(api_key="test_key", session=mock_session)
        articles = await collector.collect()
        assert len(articles) == 0

    @pytest.mark.asyncio
    async def test_collect_api_error_raises(self):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=Exception("403 Forbidden")
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        collector = CryptoPanicCollector(api_key="test_key", session=mock_session)
        with pytest.raises(Exception, match="403 Forbidden"):
            await collector.collect()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_news/test_cryptopanic_collector.py -v`
Expected: ModuleNotFoundError — `No module named 'perpetual_predict.collectors.news.cryptopanic_collector'`

- [ ] **Step 3: Create the collector**

Create `perpetual_predict/collectors/news/__init__.py`:

```python
"""News data collectors."""
```

Create `perpetual_predict/collectors/news/cryptopanic_collector.py`:

```python
"""CryptoPanic API news collector."""

from datetime import datetime, timezone

import aiohttp

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.storage.models import NewsArticle
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

CRYPTOPANIC_API_URL = "https://cryptopanic.com/api/v1/posts/"


class CryptoPanicCollector(BaseCollector):
    """Collector for crypto news from CryptoPanic API.

    Free tier: ~100 requests/day. We use ~6/day (4H intervals).
    """

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
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
        """Collect recent news from CryptoPanic.

        Returns:
            List of NewsArticle objects.
        """
        params = {
            "auth_token": self._api_key,
            "kind": "news",
            "public": "true",
        }

        async with self.session.get(CRYPTOPANIC_API_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        articles: list[NewsArticle] = []
        for item in data.get("results", []):
            article = self._parse_article(item)
            articles.append(article)

        logger.debug(f"Collected {len(articles)} articles from CryptoPanic")
        return articles

    def _parse_article(self, data: dict) -> NewsArticle:
        """Parse CryptoPanic API response item into NewsArticle."""
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_news/test_cryptopanic_collector.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Lint check**

Run: `ruff check perpetual_predict/collectors/news/`

- [ ] **Step 6: Commit**

```bash
git add perpetual_predict/collectors/news/ tests/test_news/test_cryptopanic_collector.py
git commit -m "feat: add CryptoPanic news collector"
```

---

### Task 5: RSS fallback collector

**Files:**
- Create: `perpetual_predict/collectors/news/rss_collector.py`
- Create: `tests/test_news/test_rss_collector.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_news/test_rss_collector.py`:

```python
"""Tests for RSS fallback collector."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from perpetual_predict.collectors.news.rss_collector import RSSCollector


SAMPLE_FEED = MagicMock()
SAMPLE_FEED.bozo = False
SAMPLE_FEED.entries = [
    MagicMock(
        title="Bitcoin hits new high",
        link="https://cointelegraph.com/news/btc-high",
        published_parsed=(2026, 3, 28, 8, 0, 0, 0, 0, 0),
        get=lambda key, default=None: {
            "source": MagicMock(value="CoinTelegraph"),
        }.get(key, default),
    ),
    MagicMock(
        title="Ethereum upgrade complete",
        link="https://cointelegraph.com/news/eth-upgrade",
        published_parsed=(2026, 3, 28, 7, 30, 0, 0, 0, 0),
        get=lambda key, default=None: {
            "source": MagicMock(value="CoinTelegraph"),
        }.get(key, default),
    ),
]


class TestRSSCollector:
    """Tests for RSSCollector."""

    @pytest.mark.asyncio
    async def test_collect_parses_entries(self):
        with patch("perpetual_predict.collectors.news.rss_collector.feedparser") as mock_fp:
            mock_fp.parse.return_value = SAMPLE_FEED
            collector = RSSCollector(feed_urls=["https://cointelegraph.com/rss"])
            articles = await collector.collect()

        assert len(articles) == 2
        assert articles[0].title == "Bitcoin hits new high"
        assert articles[0].votes_positive is None
        assert articles[0].collector_source == "rss"

    @pytest.mark.asyncio
    async def test_collect_empty_feed(self):
        empty_feed = MagicMock()
        empty_feed.bozo = False
        empty_feed.entries = []

        with patch("perpetual_predict.collectors.news.rss_collector.feedparser") as mock_fp:
            mock_fp.parse.return_value = empty_feed
            collector = RSSCollector(feed_urls=["https://example.com/rss"])
            articles = await collector.collect()

        assert len(articles) == 0

    @pytest.mark.asyncio
    async def test_collect_malformed_feed_continues(self):
        bad_feed = MagicMock()
        bad_feed.bozo = True
        bad_feed.entries = []

        with patch("perpetual_predict.collectors.news.rss_collector.feedparser") as mock_fp:
            mock_fp.parse.return_value = bad_feed
            collector = RSSCollector(feed_urls=["https://bad.com/rss"])
            articles = await collector.collect()

        assert len(articles) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_news/test_rss_collector.py -v`
Expected: ModuleNotFoundError — `No module named 'perpetual_predict.collectors.news.rss_collector'`

- [ ] **Step 3: Create the RSS collector**

Create `perpetual_predict/collectors/news/rss_collector.py`:

```python
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
    """Collector for crypto news via RSS feeds.

    Used as fallback when CryptoPanic API is unavailable.
    No API key required, no rate limits.
    """

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        self._feed_urls = feed_urls or DEFAULT_RSS_FEEDS

    async def collect(self, **kwargs) -> list[NewsArticle]:
        """Collect news from RSS feeds.

        Uses run_in_executor since feedparser is synchronous.

        Returns:
            List of NewsArticle objects.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._collect_sync)

    def _collect_sync(self) -> list[NewsArticle]:
        """Synchronous RSS collection logic."""
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
        """Parse RSS feed entry into NewsArticle."""
        title = getattr(entry, "title", None)
        link = getattr(entry, "link", None)
        if not title or not link:
            return None

        # Parse publish time
        published_parsed = getattr(entry, "published_parsed", None)
        if published_parsed:
            timestamp = datetime.fromtimestamp(
                timegm(published_parsed), tz=timezone.utc
            )
        else:
            timestamp = datetime.now(timezone.utc)

        # Extract source name from feed URL
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
        """Extract human-readable source name from feed URL."""
        if "cointelegraph" in feed_url:
            return "CoinTelegraph"
        if "coindesk" in feed_url:
            return "CoinDesk"
        # Fallback: use domain
        from urllib.parse import urlparse
        return urlparse(feed_url).netloc

    async def close(self) -> None:
        """No persistent connection to close."""
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_news/test_rss_collector.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Lint check**

Run: `ruff check perpetual_predict/collectors/news/rss_collector.py`

- [ ] **Step 6: Commit**

```bash
git add perpetual_predict/collectors/news/rss_collector.py tests/test_news/test_rss_collector.py
git commit -m "feat: add RSS fallback news collector"
```

---

### Task 6: News collector orchestrator (primary → fallback)

**Files:**
- Create: `perpetual_predict/collectors/news/news_collector.py`
- Create: `tests/test_news/test_news_collector.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_news/test_news_collector.py`:

```python
"""Tests for NewsCollector orchestrator."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from perpetual_predict.collectors.news.news_collector import NewsCollector
from perpetual_predict.storage.models import NewsArticle


def _make_article(title: str, source: str = "cryptopanic") -> NewsArticle:
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


class TestNewsCollector:
    """Tests for NewsCollector orchestrator."""

    @pytest.mark.asyncio
    async def test_uses_cryptopanic_when_available(self):
        cp_articles = [_make_article("CP Article")]

        collector = NewsCollector(cryptopanic_api_key="test_key")
        collector._cryptopanic = AsyncMock()
        collector._cryptopanic.collect = AsyncMock(return_value=cp_articles)
        collector._rss = AsyncMock()

        articles = await collector.collect()
        assert len(articles) == 1
        assert articles[0].title == "CP Article"
        collector._rss.collect.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_rss_on_cryptopanic_failure(self):
        rss_articles = [_make_article("RSS Article", source="rss")]

        collector = NewsCollector(cryptopanic_api_key="test_key")
        collector._cryptopanic = AsyncMock()
        collector._cryptopanic.collect = AsyncMock(side_effect=Exception("API down"))
        collector._rss = AsyncMock()
        collector._rss.collect = AsyncMock(return_value=rss_articles)

        articles = await collector.collect()
        assert len(articles) == 1
        assert articles[0].title == "RSS Article"
        assert articles[0].collector_source == "rss"

    @pytest.mark.asyncio
    async def test_uses_rss_when_no_api_key(self):
        rss_articles = [_make_article("RSS Only", source="rss")]

        collector = NewsCollector(cryptopanic_api_key="")
        collector._rss = AsyncMock()
        collector._rss.collect = AsyncMock(return_value=rss_articles)

        articles = await collector.collect()
        assert len(articles) == 1
        assert articles[0].collector_source == "rss"

    @pytest.mark.asyncio
    async def test_returns_empty_when_both_fail(self):
        collector = NewsCollector(cryptopanic_api_key="test_key")
        collector._cryptopanic = AsyncMock()
        collector._cryptopanic.collect = AsyncMock(side_effect=Exception("API down"))
        collector._rss = AsyncMock()
        collector._rss.collect = AsyncMock(side_effect=Exception("RSS down"))

        articles = await collector.collect()
        assert len(articles) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_news/test_news_collector.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: Create the orchestrator**

Create `perpetual_predict/collectors/news/news_collector.py`:

```python
"""News collector orchestrator with CryptoPanic primary and RSS fallback."""

from perpetual_predict.collectors.base_collector import BaseCollector
from perpetual_predict.collectors.news.cryptopanic_collector import CryptoPanicCollector
from perpetual_predict.collectors.news.rss_collector import RSSCollector
from perpetual_predict.storage.models import NewsArticle
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class NewsCollector(BaseCollector):
    """Orchestrator: CryptoPanic (primary) → RSS (fallback).

    Falls back to RSS if CryptoPanic fails or no API key is provided.
    """

    def __init__(
        self,
        cryptopanic_api_key: str = "",
        rss_feed_urls: list[str] | None = None,
    ) -> None:
        self._cryptopanic = (
            CryptoPanicCollector(api_key=cryptopanic_api_key)
            if cryptopanic_api_key
            else None
        )
        self._rss = RSSCollector(feed_urls=rss_feed_urls)
        self._used_fallback = False

    @property
    def used_fallback(self) -> bool:
        """Whether the last collection used RSS fallback."""
        return self._used_fallback

    async def collect(self, **kwargs) -> list[NewsArticle]:
        """Collect news: try CryptoPanic first, fall back to RSS.

        Returns:
            List of NewsArticle objects.
        """
        self._used_fallback = False

        # Try CryptoPanic first
        if self._cryptopanic:
            try:
                articles = await self._cryptopanic.collect()
                logger.info(f"Collected {len(articles)} articles from CryptoPanic")
                return articles
            except Exception as e:
                logger.warning(f"CryptoPanic failed, falling back to RSS: {e}")

        # Fallback to RSS
        self._used_fallback = True
        try:
            articles = await self._rss.collect()
            logger.info(f"Collected {len(articles)} articles from RSS (fallback)")
            return articles
        except Exception as e:
            logger.error(f"RSS fallback also failed: {e}")
            return []

    async def close(self) -> None:
        """Close all sub-collectors."""
        if self._cryptopanic:
            await self._cryptopanic.close()
        await self._rss.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_news/test_news_collector.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Lint check**

Run: `ruff check perpetual_predict/collectors/news/news_collector.py`

- [ ] **Step 6: Commit**

```bash
git add perpetual_predict/collectors/news/news_collector.py tests/test_news/test_news_collector.py
git commit -m "feat: add news collector orchestrator with RSS fallback"
```

---

### Task 7: Settings, module registration, and collect CLI integration

**Files:**
- Modify: `perpetual_predict/config/settings.py` (CryptoPanicConfig — add max_headlines, news_enabled)
- Modify: `perpetual_predict/experiment/models.py` (SEED_MODULES, EXPERIMENTAL_MODULES)
- Modify: `perpetual_predict/cli/collect.py` (add news to gather)
- Modify: `perpetual_predict/notifications/scheduler_alerts.py` (add news line)

- [ ] **Step 1: Update CryptoPanicConfig**

In `perpetual_predict/config/settings.py`, modify the existing `CryptoPanicConfig` (line 79):

```python
@dataclass
class CryptoPanicConfig:
    """CryptoPanic API configuration."""

    api_key: str = ""
    base_url: str = "https://cryptopanic.com/api/v1"
    filter_currencies: str = "BTC"  # Comma-separated currency codes
    news_enabled: bool = True
    max_headlines: int = 100
    rss_feeds: str = "https://cointelegraph.com/rss,https://www.coindesk.com/arc/outboundfeeds/rss/"
```

In `from_env()` method (around line 226), update the CryptoPanic section:

```python
            cryptopanic=CryptoPanicConfig(
                api_key=os.getenv("CRYPTOPANIC_API_KEY", ""),
                filter_currencies=os.getenv("CRYPTOPANIC_CURRENCIES", "BTC"),
                news_enabled=os.getenv("NEWS_ENABLED", "true").lower() == "true",
                max_headlines=int(os.getenv("NEWS_MAX_HEADLINES", "100")),
                rss_feeds=os.getenv(
                    "NEWS_RSS_FEEDS",
                    "https://cointelegraph.com/rss,https://www.coindesk.com/arc/outboundfeeds/rss/",
                ),
            ),
```

- [ ] **Step 2: Register news module**

In `perpetual_predict/experiment/models.py`:

Add `"news"` to `SEED_MODULES` (after line 25 `"macro"`):

```python
    "news",
```

Change `EXPERIMENTAL_MODULES` (line 30) to:

```python
EXPERIMENTAL_MODULES = {"macro", "news"}
```

- [ ] **Step 3: Add news collector to collect CLI**

In `perpetual_predict/cli/collect.py`:

After the macro collectors section (after line 68), add:

```python
    # News collector
    news_collector = None
    if settings.cryptopanic.news_enabled:
        from perpetual_predict.collectors.news.news_collector import NewsCollector

        rss_feeds = [u.strip() for u in settings.cryptopanic.rss_feeds.split(",") if u.strip()]
        news_collector = NewsCollector(
            cryptopanic_api_key=settings.cryptopanic.api_key,
            rss_feed_urls=rss_feeds,
        )
```

Modify the `asyncio.gather()` call (lines 84-93). Add news task:

```python
        news_task = [news_collector.collect()] if news_collector else []
        api_results = await asyncio.gather(
            ohlcv_collector.collect(start_time=start_time, end_time=end_time),
            funding_collector.collect(start_time=start_time, end_time=end_time),
            oi_collector.collect(limit=oi_limit),
            ls_collector.collect(limit=ls_limit),
            fgi_collector.collect(limit=days),
            *macro_tasks,
            *news_task,
            return_exceptions=True,
        )
```

Update results extraction (lines 95-96):

```python
        candles, funding_rates, open_interests, ratios, fgi_data = api_results[:5]
        macro_results = api_results[5:5 + len(macro_tasks)]
        news_result = api_results[5 + len(macro_tasks)] if news_collector else None
```

After the macro handling block (after line 162), add news handling:

```python
            # Handle news articles
            if news_result is not None:
                if isinstance(news_result, Exception):
                    logger.error(f"Failed to collect news: {news_result}")
                    results["news_articles"] = 0
                else:
                    if news_result:
                        await db.insert_news_articles(news_result)
                    results["news_articles"] = len(news_result)
                    source = "rss fallback" if news_collector and news_collector.used_fallback else "cryptopanic"
                    logger.info(f"Collected {len(news_result)} news articles ({source})")
            else:
                results["news_articles"] = 0
```

In the `finally` block (after line 168), add:

```python
        if news_collector:
            await news_collector.close()
```

In `run_collect()` output (after line 199), add:

```python
        print(f"  News Articles: {results.get('news_articles', 0)}")
```

- [ ] **Step 4: Update Discord notifications**

In `perpetual_predict/notifications/scheduler_alerts.py`, add to `results_lines` (after line 99):

```python
        f"• 뉴스기사: `{results.get('news_articles', 0)}`개",
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --timeout=30`
Expected: All existing tests still pass

- [ ] **Step 6: Lint check**

Run: `ruff check perpetual_predict/config/settings.py perpetual_predict/experiment/models.py perpetual_predict/cli/collect.py perpetual_predict/notifications/scheduler_alerts.py`

- [ ] **Step 7: Commit**

```bash
git add perpetual_predict/config/settings.py perpetual_predict/experiment/models.py perpetual_predict/cli/collect.py perpetual_predict/notifications/scheduler_alerts.py
git commit -m "feat: integrate news collector into settings, CLI, and module system"
```

---

### Task 8: Context builder — _section_news() and MarketContext integration

**Files:**
- Modify: `perpetual_predict/llm/context/builder.py`
- Create: `tests/test_news/test_context_news.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_news/test_context_news.py`:

```python
"""Tests for news section in context builder."""

from datetime import datetime, timezone

from perpetual_predict.llm.context.builder import MarketContext
from perpetual_predict.storage.models import NewsArticle


def _make_articles(count: int, source: str = "cryptopanic") -> list[NewsArticle]:
    articles = []
    for i in range(count):
        articles.append(NewsArticle(
            timestamp=datetime(2026, 3, 28, 8 - i, 0, tzinfo=timezone.utc),
            title=f"Headline {i}",
            source=f"Source{i}",
            url=f"https://example.com/{i}",
            votes_positive=10 + i if source == "cryptopanic" else None,
            votes_negative=2 + i if source == "cryptopanic" else None,
            votes_important=5 + i if source == "cryptopanic" else None,
            collected_at=datetime(2026, 3, 28, 8, 1, tzinfo=timezone.utc),
            collector_source=source,
        ))
    return articles


class TestSectionNews:
    """Tests for _section_news() method."""

    def test_section_news_with_articles(self):
        articles = _make_articles(3)
        ctx = MarketContext(
            current_price=87000.0,
            price_change_4h=1.5,
            price_change_24h=3.0,
            high_24h=88000.0,
            low_24h=86000.0,
            volume_24h=5000.0,
            news_articles=articles,
        )
        section = ctx._section_news()
        assert "### News" in section
        assert "Headline 0" in section
        assert "Headline 2" in section
        assert "+10/-2" in section  # votes for first article

    def test_section_news_empty(self):
        ctx = MarketContext(
            current_price=87000.0,
            price_change_4h=1.5,
            price_change_24h=3.0,
            high_24h=88000.0,
            low_24h=86000.0,
            volume_24h=5000.0,
            news_articles=[],
        )
        section = ctx._section_news()
        assert section == ""

    def test_section_news_rss_without_votes(self):
        articles = _make_articles(2, source="rss")
        ctx = MarketContext(
            current_price=87000.0,
            price_change_4h=1.5,
            price_change_24h=3.0,
            high_24h=88000.0,
            low_24h=86000.0,
            volume_24h=5000.0,
            news_articles=articles,
        )
        section = ctx._section_news()
        assert "via RSS" in section

    def test_section_news_respects_max_headlines(self):
        articles = _make_articles(120)
        ctx = MarketContext(
            current_price=87000.0,
            price_change_4h=1.5,
            price_change_24h=3.0,
            high_24h=88000.0,
            low_24h=86000.0,
            volume_24h=5000.0,
            news_articles=articles,
            news_max_headlines=100,
        )
        section = ctx._section_news()
        assert "120 total" in section
        assert "100 most recent" in section
        # Should summarize the older 20
        assert "20" in section

    def test_format_prompt_includes_news_when_enabled(self):
        articles = _make_articles(2)
        ctx = MarketContext(
            current_price=87000.0,
            price_change_4h=1.5,
            price_change_24h=3.0,
            high_24h=88000.0,
            low_24h=86000.0,
            volume_24h=5000.0,
            news_articles=articles,
        )
        prompt = ctx.format_prompt(enabled_modules=["news"])
        assert "### News" in prompt

    def test_format_prompt_excludes_news_when_not_enabled(self):
        articles = _make_articles(2)
        ctx = MarketContext(
            current_price=87000.0,
            price_change_4h=1.5,
            price_change_24h=3.0,
            high_24h=88000.0,
            low_24h=86000.0,
            volume_24h=5000.0,
            news_articles=articles,
        )
        prompt = ctx.format_prompt(enabled_modules=["price_action"])
        assert "### News" not in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_news/test_context_news.py -v`
Expected: TypeError — `MarketContext.__init__() got an unexpected keyword argument 'news_articles'`

- [ ] **Step 3: Add news fields to MarketContext**

In `perpetual_predict/llm/context/builder.py`, add to the MarketContext dataclass after the Fear & Greed fields (after line 98):

```python
    # News articles (raw data for prompt)
    news_articles: list = field(default_factory=list)
    news_max_headlines: int = 100
```

Add the `from perpetual_predict.storage.models import NewsArticle` import at the top if not already present. (It may need to go alongside the existing model imports.)

- [ ] **Step 4: Add _section_news() method**

In `perpetual_predict/llm/context/builder.py`, add after `_section_macro()` (after line 342):

```python
    def _section_news(self) -> str:
        """Format news section with raw data only."""
        if not self.news_articles:
            return ""

        total = len(self.news_articles)
        max_h = self.news_max_headlines

        # Aggregate vote totals
        total_positive = sum(a.votes_positive or 0 for a in self.news_articles)
        total_negative = sum(a.votes_negative or 0 for a in self.news_articles)
        total_important = sum(a.votes_important or 0 for a in self.news_articles)

        lines = ["### News (Recent 4H)"]

        if total <= max_h:
            lines.append(f"Articles: {total} total")
        else:
            lines.append(f"Articles: {total} total (showing {max_h} most recent, {total - max_h} older summarized)")

        # Show vote summary if any CryptoPanic articles
        has_votes = any(a.votes_positive is not None for a in self.news_articles)
        if has_votes:
            lines.append(f"Sentiment votes: +{total_positive} positive, -{total_negative} negative, {total_important} important")

        lines.append("")
        lines.append("Headlines:")

        # Show headlines (up to max_headlines)
        display_articles = self.news_articles[:max_h]
        for a in display_articles:
            ts_str = a.timestamp.strftime("%Y-%m-%d %H:%M")
            if a.votes_positive is not None:
                vote_str = f", +{a.votes_positive}/-{a.votes_negative}, important: {a.votes_important}"
            else:
                vote_str = ", via RSS"
            lines.append(f"- [{ts_str}] \"{a.title}\" (src: {a.source}{vote_str})")

        # Summarize older articles if truncated
        if total > max_h:
            older = self.news_articles[max_h:]
            older_pos = sum(a.votes_positive or 0 for a in older)
            older_neg = sum(a.votes_negative or 0 for a in older)
            older_imp = sum(a.votes_important or 0 for a in older)
            lines.append(f"\nOlder articles ({len(older)}): +{older_pos} positive, -{older_neg} negative, {older_imp} important")

        return "\n".join(lines)
```

- [ ] **Step 5: Add news module check in format_prompt()**

In `format_prompt()` (around line 182), add after the `macro` check:

```python
        if "news" in modules:
            sections.append(self._section_news())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_news/test_context_news.py -v`
Expected: All 6 tests PASS

- [ ] **Step 7: Lint check**

Run: `ruff check perpetual_predict/llm/context/builder.py tests/test_news/test_context_news.py`

- [ ] **Step 8: Commit**

```bash
git add perpetual_predict/llm/context/builder.py tests/test_news/test_context_news.py
git commit -m "feat: add _section_news() to context builder with max headlines"
```

---

### Task 9: Wire news data into MarketContextBuilder.build()

**Files:**
- Modify: `perpetual_predict/llm/context/builder.py` (build() method)

- [ ] **Step 1: Add news data fetch in build()**

In `perpetual_predict/llm/context/builder.py`, in the `build()` method, after the `macro_snapshot` fetch (line 474):

```python
        news_articles = await self.db.get_recent_news(hours=4)
```

- [ ] **Step 2: Add news_articles to MarketContext instantiation**

In the `return MarketContext(...)` block, add before `symbol=self.symbol` (around line 575):

```python
            # News articles
            news_articles=news_articles,
            news_max_headlines=self._get_max_headlines(),
```

- [ ] **Step 3: Add helper method for max_headlines config**

Add after the existing helper methods:

```python
    def _get_max_headlines(self) -> int:
        """Get max headlines from settings."""
        try:
            from perpetual_predict.config import get_settings
            return get_settings().cryptopanic.max_headlines
        except Exception:
            return 100
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v --timeout=30`
Expected: All tests pass

- [ ] **Step 5: Lint check**

Run: `ruff check perpetual_predict/llm/context/builder.py`

- [ ] **Step 6: Commit**

```bash
git add perpetual_predict/llm/context/builder.py
git commit -m "feat: wire news data into MarketContextBuilder.build()"
```

---

### Task 10: Data integrity verification for news

**Files:**
- Modify: `perpetual_predict/reporters/data_integrity.py`

- [ ] **Step 1: Add news fields to LatestDataVerification**

In `perpetual_predict/reporters/data_integrity.py`, in the `LatestDataVerification` dataclass (after `macro_daily` around line 398):

```python
    # News articles (보조 — 사이클 비블로킹)
    news_4h: bool = False
    news_article_count: int = 0
    news_collector_source: str = ""
```

- [ ] **Step 2: Update verified_count**

In the `verified_count` property (around line 437), add `self.news_4h` to the sum list:

```python
            self.macro_daily,
            self.news_4h,
```

- [ ] **Step 3: Update total_types**

Change `total_types` (line 443) from `return 5` to `return 6`.

- [ ] **Step 4: Update missing_data**

In the `missing_data` property, add after the macro check:

```python
        if not self.news_4h:
            missing.append("News (4H)")
```

- [ ] **Step 5: Add news verification to verify_latest_data()**

After the macro verification section (around line 617), add:

```python
    # 6. News articles (4H freshness)
    news_articles = await db.get_recent_news(hours=4)
    if news_articles:
        result.news_article_count = len(news_articles)
        result.news_collector_source = news_articles[0].collector_source
        result.news_4h = True
```

- [ ] **Step 6: Update log output**

Update the log message at line 622 to include news:

```python
            f"{', Macro' if result.macro_daily else ''}"
            f"{', News' if result.news_4h else ''} "
```

- [ ] **Step 7: Run existing tests**

Run: `pytest tests/ -v --timeout=30`
Expected: All tests pass

- [ ] **Step 8: Lint check**

Run: `ruff check perpetual_predict/reporters/data_integrity.py`

- [ ] **Step 9: Commit**

```bash
git add perpetual_predict/reporters/data_integrity.py
git commit -m "feat: add news data verification to integrity reporter"
```

---

### Task 11: Full integration test and final cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All tests pass, including new tests in `tests/test_news/`

- [ ] **Step 2: Run linter on all changed files**

Run: `ruff check perpetual_predict/ tests/`

- [ ] **Step 3: Verify module registration**

Run: `python -c "from perpetual_predict.experiment.models import SEED_MODULES, EXPERIMENTAL_MODULES, DEFAULT_MODULES; print('SEED:', SEED_MODULES); print('EXP:', EXPERIMENTAL_MODULES); print('DEFAULT:', DEFAULT_MODULES)"`

Expected: `news` in SEED_MODULES, `news` in EXPERIMENTAL_MODULES, `news` NOT in DEFAULT_MODULES

- [ ] **Step 4: Verify import chain**

Run: `python -c "from perpetual_predict.collectors.news.news_collector import NewsCollector; print('NewsCollector imported OK')"`

Expected: `NewsCollector imported OK`

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: add comprehensive news module integration tests"
```
