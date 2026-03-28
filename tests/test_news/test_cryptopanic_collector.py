"""Tests for CryptoPanicCollector."""

from unittest.mock import AsyncMock, MagicMock

import pytest

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


def _make_mock_response(json_data=None, raise_error=None):
    """Build a mock aiohttp response context manager."""
    mock_response = MagicMock()
    if raise_error is not None:
        mock_response.raise_for_status.side_effect = raise_error
    else:
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=json_data)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_collect_parses_articles():
    """Collector returns correctly parsed articles from API response."""
    from perpetual_predict.collectors.news.cryptopanic_collector import (
        CryptoPanicCollector,
    )

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value = _make_mock_response(json_data=SAMPLE_RESPONSE)

    collector = CryptoPanicCollector(api_key="test-key", session=mock_session)
    articles = await collector.collect()

    assert len(articles) == 2

    first = articles[0]
    assert first.title == "Bitcoin ETF sees record inflow"
    assert first.url == "https://example.com/btc-etf"
    assert first.source == "CoinDesk"
    assert first.votes_positive == 18
    assert first.votes_negative == 2
    assert first.votes_important == 5
    assert first.collector_source == "cryptopanic"
    assert first.timestamp.year == 2026
    assert first.timestamp.month == 3
    assert first.timestamp.day == 28

    second = articles[1]
    assert second.title == "New DeFi protocol launches"
    assert second.source == "CryptoSlate"
    assert second.votes_positive == 5


@pytest.mark.asyncio
async def test_collect_empty_response():
    """Collector returns empty list when API returns no results."""
    from perpetual_predict.collectors.news.cryptopanic_collector import (
        CryptoPanicCollector,
    )

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value = _make_mock_response(json_data={"results": []})

    collector = CryptoPanicCollector(api_key="test-key", session=mock_session)
    articles = await collector.collect()

    assert articles == []


@pytest.mark.asyncio
async def test_collect_api_error_raises():
    """Collector propagates exception when raise_for_status raises."""
    from perpetual_predict.collectors.news.cryptopanic_collector import (
        CryptoPanicCollector,
    )

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value = _make_mock_response(
        raise_error=Exception("HTTP 401 Unauthorized")
    )

    collector = CryptoPanicCollector(api_key="bad-key", session=mock_session)

    with pytest.raises(Exception, match="HTTP 401 Unauthorized"):
        await collector.collect()
