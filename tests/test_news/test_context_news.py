"""Tests for news section in context builder."""

from datetime import datetime, timezone

from perpetual_predict.llm.context.builder import MarketContext
from perpetual_predict.storage.models import NewsArticle


def _make_articles(count, source="cryptopanic"):
    articles = []
    for i in range(count):
        articles.append(NewsArticle(
            timestamp=datetime(2026, 3, 28, 8, 0, tzinfo=timezone.utc),
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


def _make_context(**kwargs):
    defaults = dict(
        current_price=87000.0,
        price_change_4h=1.5,
        price_change_24h=3.0,
        high_24h=88000.0,
        low_24h=86000.0,
        volume_24h=5000.0,
    )
    defaults.update(kwargs)
    return MarketContext(**defaults)


def test_section_news_with_articles():
    articles = _make_articles(3)
    ctx = _make_context(news_articles=articles)
    output = ctx._section_news()
    assert "### News" in output
    assert "Headline 0" in output
    assert "Headline 1" in output
    assert "Headline 2" in output
    assert "+10/-2" in output


def test_section_news_empty():
    ctx = _make_context(news_articles=[])
    assert ctx._section_news() == ""


def test_section_news_rss_without_votes():
    articles = _make_articles(2, source="rss")
    ctx = _make_context(news_articles=articles)
    output = ctx._section_news()
    assert "via RSS" in output


def test_section_news_respects_max_headlines():
    articles = _make_articles(120)
    ctx = _make_context(news_articles=articles, news_max_headlines=100)
    output = ctx._section_news()
    assert "120 total" in output
    assert "100 most recent" in output
    # Older articles summary
    assert "20" in output


def test_format_prompt_includes_news_when_enabled():
    articles = _make_articles(3)
    ctx = _make_context(news_articles=articles)
    output = ctx.format_prompt(enabled_modules=["news"])
    assert "### News" in output


def test_format_prompt_excludes_news_when_not_enabled():
    articles = _make_articles(3)
    ctx = _make_context(news_articles=articles)
    output = ctx.format_prompt(enabled_modules=["price_action"])
    assert "### News" not in output
