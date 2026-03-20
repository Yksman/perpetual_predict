#!/usr/bin/env python3
"""Quick test for all collectors.

Usage:
    python scripts/test_collectors.py
"""

import asyncio


async def test_all():
    print("=" * 60)
    print("Perpetual Predict - Collector Quick Test")
    print("=" * 60)

    # 1. OHLCV
    print("\n[1] OHLCV Collector")
    try:
        from perpetual_predict.collectors.binance.market_data import OHLCVCollector

        collector = OHLCVCollector()
        candles = await collector.collect(limit=3)
        print(f"    OK - {len(candles)} candles collected")
        if candles:
            c = candles[0]
            print(f"    Latest: {c.open_time} | Close: {c.close:,.2f}")
        await collector.close()
    except Exception as e:
        print(f"    FAIL - {e}")

    # 2. Long/Short Ratio
    print("\n[2] Long/Short Ratio Collector")
    try:
        from perpetual_predict.collectors.binance.market_data import LongShortRatioCollector

        collector = LongShortRatioCollector()
        ratios = await collector.collect(limit=3)
        print(f"    OK - {len(ratios)} records collected")
        if ratios:
            r = ratios[0]
            print(f"    Latest: Long {r.long_ratio*100:.1f}% / Short {r.short_ratio*100:.1f}%")
        await collector.close()
    except Exception as e:
        print(f"    FAIL - {e}")

    # 3. Funding Rate
    print("\n[3] Funding Rate Collector")
    try:
        from perpetual_predict.collectors.binance.funding import FundingRateCollector

        collector = FundingRateCollector()
        current = await collector.collect_current()
        if current:
            print(f"    OK - Current rate: {current.funding_rate:.6f} ({current.funding_rate*100:.4f}%)")
        else:
            print("    WARN - No data available")
        await collector.close()
    except Exception as e:
        print(f"    FAIL - {e}")

    # 4. Open Interest
    print("\n[4] Open Interest Collector")
    try:
        from perpetual_predict.collectors.binance.open_interest import OpenInterestCollector

        collector = OpenInterestCollector()
        current = await collector.collect_current()
        print(f"    OK - Current OI: {current.open_interest:,.2f} BTC")
        await collector.close()
    except Exception as e:
        print(f"    FAIL - {e}")

    # 5. Fear & Greed
    print("\n[5] Fear & Greed Collector")
    try:
        from perpetual_predict.collectors.sentiment.fear_greed import FearGreedCollector

        collector = FearGreedCollector()
        current = await collector.collect_current()
        if current:
            print(f"    OK - Value: {current.value} ({current.classification})")
        else:
            print("    WARN - No data available")
        await collector.close()
    except Exception as e:
        print(f"    FAIL - {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all())
