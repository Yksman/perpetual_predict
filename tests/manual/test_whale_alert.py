"""US-25: Whale Alert Collector 테스트."""

import asyncio

from perpetual_predict.collectors.onchain.whale_alert import WhaleAlertCollector
from perpetual_predict.storage.database import Database


async def main():
    db = Database()
    await db.initialize()

    collector = WhaleAlertCollector()

    if not collector.api_key:
        print("❌ WHALE_ALERT_API_KEY 환경변수가 설정되지 않았습니다")
        print("   https://whale-alert.io 에서 API 키를 발급받으세요")
        await db.close()
        return

    print("=== Whale Alert 테스트 ===")

    # 최근 1시간 내 대규모 거래 조회
    transactions = await collector.collect(limit=5)

    print(f"수집된 고래 거래: {len(transactions)}건")
    for tx in transactions:
        print(f"  - {tx.blockchain}: {tx.amount:,.0f} {tx.symbol}")
        print(f"    {tx.from_owner} -> {tx.to_owner}")
        print(f"    가치: ${tx.amount_usd:,.0f}")
        print()

    # DB 저장 테스트
    if transactions:
        await db.insert_whale_transactions(transactions)
        print("✅ DB 저장 완료")
    else:
        print("⚠️ 최근 고래 거래 없음 (시장 상황에 따라 정상)")

    await db.close()
    await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
