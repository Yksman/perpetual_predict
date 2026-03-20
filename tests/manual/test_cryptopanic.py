"""US-26: CryptoPanic News Collector 테스트."""

import asyncio

from perpetual_predict.collectors.news.cryptopanic import CryptoPanicCollector
from perpetual_predict.storage.database import Database


async def main():
    db = Database()
    await db.initialize()

    collector = CryptoPanicCollector()

    if not collector.api_key:
        print("❌ CRYPTOPANIC_API_KEY 환경변수가 설정되지 않았습니다")
        print("   https://cryptopanic.com/developers/api/ 에서 API 키를 발급받으세요")
        await db.close()
        return

    print("=== CryptoPanic News 테스트 ===")

    # 최근 뉴스 조회
    news_items = await collector.collect(limit=5)

    print(f"수집된 뉴스: {len(news_items)}건\n")
    for item in news_items:
        sentiment_emoji = {"positive": "O", "negative": "X", "neutral": "-"}.get(
            item.sentiment, "-"
        )

        print(f"[{sentiment_emoji}] [{item.kind}] {item.title}")
        print(f"   소스: {item.source} | 투표: +{item.votes_positive} -{item.votes_negative}")
        print(f"   URL: {item.url}")
        print()

    # DB 저장 테스트
    if news_items:
        await db.insert_news_items(news_items)
        print("✅ DB 저장 완료")
    else:
        print("⚠️ 뉴스 없음")

    await db.close()
    await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
