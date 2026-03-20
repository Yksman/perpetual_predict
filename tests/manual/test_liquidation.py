"""US-21: Liquidation Collector 테스트."""

import asyncio

from perpetual_predict.collectors.binance.liquidation import LiquidationCollector
from perpetual_predict.storage.database import Database


async def main():
    db = Database()
    await db.initialize()

    collector = LiquidationCollector()

    print("=== Liquidation Collector 테스트 ===")

    # 최근 청산 데이터 수집
    liquidations = await collector.collect(limit=10)

    print(f"수집된 청산 건수: {len(liquidations)}")
    for liq in liquidations[:3]:
        print(f"  - {liq.side} {liq.original_qty} @ ${liq.price:,.2f} ({liq.timestamp})")

    # DB 저장 테스트
    if liquidations:
        await db.insert_liquidations(liquidations)
        print("✅ DB 저장 완료")
    else:
        print("⚠️ 수집된 청산 데이터 없음 (시장 상황에 따라 정상)")

    await db.close()
    await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
