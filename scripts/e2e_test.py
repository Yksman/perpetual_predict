#!/usr/bin/env python3
"""E2E Test for 5 data sources collection.

Test Symbol: BTCUSDT (Binance Futures uses BTCUSDT not BTCUSDT.P)
Test Timeframe: 4H

Validates:
1. Data schema correctness
2. Data quality and completeness
3. All 5 collectors working properly
"""

import asyncio
import sys
from dataclasses import fields
from datetime import datetime, timezone


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: str | None = None
        self.data_count = 0
        self.schema_valid = False
        self.data_quality_issues: list[str] = []

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        details = f"count={self.data_count}, schema_valid={self.schema_valid}"
        if self.error:
            details += f", error={self.error}"
        if self.data_quality_issues:
            details += f", issues={self.data_quality_issues}"
        return f"[{status}] {self.name}: {details}"


def validate_schema(obj, expected_fields: list[str]) -> tuple[bool, list[str]]:
    """Validate object has all expected fields with non-null values."""
    issues = []
    obj_fields = {f.name for f in fields(obj)}

    for field in expected_fields:
        if field not in obj_fields:
            issues.append(f"Missing field: {field}")
        else:
            value = getattr(obj, field)
            if value is None:
                issues.append(f"Null value: {field}")

    return len(issues) == 0, issues


async def test_ohlcv_collector() -> TestResult:
    """Test OHLCV Collector."""
    from perpetual_predict.collectors.binance.market_data import OHLCVCollector

    result = TestResult("OHLCVCollector")

    try:
        collector = OHLCVCollector(symbol="BTCUSDT", timeframe="4h")
        candles = await collector.collect(limit=10)
        await collector.close()

        result.data_count = len(candles)

        if not candles:
            result.error = "No candles returned"
            return result

        # Validate schema
        expected_fields = [
            "symbol", "timeframe", "open_time", "open", "high", "low",
            "close", "volume", "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote"
        ]

        candle = candles[0]
        schema_valid, schema_issues = validate_schema(candle, expected_fields)
        result.schema_valid = schema_valid
        result.data_quality_issues.extend(schema_issues)

        # Validate data quality
        for i, c in enumerate(candles):
            if c.high < c.low:
                result.data_quality_issues.append(f"Candle {i}: high < low")
            if c.close < 0 or c.open < 0:
                result.data_quality_issues.append(f"Candle {i}: negative price")
            if c.volume < 0:
                result.data_quality_issues.append(f"Candle {i}: negative volume")
            if c.symbol != "BTCUSDT":
                result.data_quality_issues.append(f"Candle {i}: wrong symbol {c.symbol}")
            if c.timeframe != "4h":
                result.data_quality_issues.append(f"Candle {i}: wrong timeframe {c.timeframe}")

        result.passed = schema_valid and len(result.data_quality_issues) == 0 and result.data_count > 0

    except Exception as e:
        result.error = str(e)

    return result


async def test_long_short_ratio_collector() -> TestResult:
    """Test Long/Short Ratio Collector."""
    from perpetual_predict.collectors.binance.market_data import LongShortRatioCollector

    result = TestResult("LongShortRatioCollector")

    try:
        collector = LongShortRatioCollector(symbol="BTCUSDT", period="4h")
        ratios = await collector.collect(limit=10)
        await collector.close()

        result.data_count = len(ratios)

        if not ratios:
            result.error = "No ratios returned"
            return result

        # Validate schema
        expected_fields = ["symbol", "timestamp", "long_ratio", "short_ratio", "long_short_ratio"]

        ratio = ratios[0]
        schema_valid, schema_issues = validate_schema(ratio, expected_fields)
        result.schema_valid = schema_valid
        result.data_quality_issues.extend(schema_issues)

        # Validate data quality
        for i, r in enumerate(ratios):
            if r.long_ratio < 0 or r.long_ratio > 1:
                result.data_quality_issues.append(f"Ratio {i}: invalid long_ratio {r.long_ratio}")
            if r.short_ratio < 0 or r.short_ratio > 1:
                result.data_quality_issues.append(f"Ratio {i}: invalid short_ratio {r.short_ratio}")
            if abs(r.long_ratio + r.short_ratio - 1.0) > 0.01:
                result.data_quality_issues.append(f"Ratio {i}: long+short != 1.0")

        result.passed = schema_valid and len(result.data_quality_issues) == 0 and result.data_count > 0

    except Exception as e:
        result.error = str(e)

    return result


async def test_funding_rate_collector() -> TestResult:
    """Test Funding Rate Collector."""
    from perpetual_predict.collectors.binance.funding import FundingRateCollector

    result = TestResult("FundingRateCollector")

    try:
        collector = FundingRateCollector(symbol="BTCUSDT")

        # Test collect_current
        current = await collector.collect_current()

        # Test collect history
        rates = await collector.collect(limit=10)
        await collector.close()

        result.data_count = len(rates) + (1 if current else 0)

        if not rates and not current:
            result.error = "No funding rates returned"
            return result

        # Validate schema
        expected_fields = ["symbol", "funding_time", "funding_rate", "mark_price"]

        test_obj = current if current else rates[0]
        schema_valid, schema_issues = validate_schema(test_obj, expected_fields)
        result.schema_valid = schema_valid
        result.data_quality_issues.extend(schema_issues)

        # Validate data quality
        for i, r in enumerate(rates):
            # Funding rate typically between -0.75% and 0.75%
            if abs(r.funding_rate) > 0.01:
                result.data_quality_issues.append(f"Rate {i}: unusual funding_rate {r.funding_rate}")
            if r.mark_price <= 0:
                result.data_quality_issues.append(f"Rate {i}: invalid mark_price {r.mark_price}")

        result.passed = schema_valid and len(result.data_quality_issues) == 0 and result.data_count > 0

    except Exception as e:
        result.error = str(e)

    return result


async def test_open_interest_collector() -> TestResult:
    """Test Open Interest Collector."""
    from perpetual_predict.collectors.binance.open_interest import OpenInterestCollector

    result = TestResult("OpenInterestCollector")

    try:
        collector = OpenInterestCollector(symbol="BTCUSDT", period="4h")

        # Test collect_current
        current = await collector.collect_current()

        # Test collect history
        ois = await collector.collect(limit=10)
        await collector.close()

        result.data_count = len(ois) + (1 if current else 0)

        if not ois and not current:
            result.error = "No open interest data returned"
            return result

        # Validate schema
        expected_fields = ["symbol", "timestamp", "open_interest", "open_interest_value"]

        schema_valid, schema_issues = validate_schema(current, expected_fields)
        result.schema_valid = schema_valid
        result.data_quality_issues.extend(schema_issues)

        # Validate data quality
        if current:
            if current.open_interest <= 0:
                result.data_quality_issues.append(f"Current OI: invalid open_interest {current.open_interest}")

        for i, oi in enumerate(ois):
            if oi.open_interest <= 0:
                result.data_quality_issues.append(f"OI {i}: invalid open_interest {oi.open_interest}")
            if oi.open_interest_value < 0:
                result.data_quality_issues.append(f"OI {i}: negative open_interest_value")

        result.passed = schema_valid and len(result.data_quality_issues) == 0 and result.data_count > 0

    except Exception as e:
        result.error = str(e)

    return result


async def test_fear_greed_collector() -> TestResult:
    """Test Fear & Greed Collector."""
    from perpetual_predict.collectors.sentiment.fear_greed import FearGreedCollector

    result = TestResult("FearGreedCollector")

    try:
        collector = FearGreedCollector()

        # Test collect_current
        current = await collector.collect_current()

        # Test collect history
        history = await collector.collect(limit=7)
        await collector.close()

        result.data_count = len(history) + (1 if current else 0)

        if not history and not current:
            result.error = "No fear & greed data returned"
            return result

        # Validate schema
        expected_fields = ["timestamp", "value", "classification"]

        test_obj = current if current else history[0]
        schema_valid, schema_issues = validate_schema(test_obj, expected_fields)
        result.schema_valid = schema_valid
        result.data_quality_issues.extend(schema_issues)

        # Validate data quality
        valid_classifications = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]

        if current:
            if not (0 <= current.value <= 100):
                result.data_quality_issues.append(f"Current: invalid value {current.value}")
            if current.classification not in valid_classifications:
                result.data_quality_issues.append(f"Current: invalid classification {current.classification}")

        for i, fg in enumerate(history):
            if not (0 <= fg.value <= 100):
                result.data_quality_issues.append(f"FG {i}: invalid value {fg.value}")
            if fg.classification not in valid_classifications:
                result.data_quality_issues.append(f"FG {i}: invalid classification {fg.classification}")

        result.passed = schema_valid and len(result.data_quality_issues) == 0 and result.data_count > 0

    except Exception as e:
        result.error = str(e)

    return result


async def run_all_tests() -> list[TestResult]:
    """Run all E2E tests."""
    print("=" * 70)
    print("E2E Test: Binance API Data Collection")
    print(f"Test Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Symbol: BTCUSDT, Timeframe: 4H")
    print("=" * 70)

    tests = [
        ("OHLCV", test_ohlcv_collector),
        ("Long/Short Ratio", test_long_short_ratio_collector),
        ("Funding Rate", test_funding_rate_collector),
        ("Open Interest", test_open_interest_collector),
        ("Fear & Greed", test_fear_greed_collector),
    ]

    results = []

    for name, test_func in tests:
        print(f"\nTesting {name}...")
        result = await test_func()
        results.append(result)
        print(f"  {result}")

    return results


def print_summary(results: list[TestResult]) -> bool:
    """Print test summary and return overall pass/fail."""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}")
        if not r.passed:
            if r.error:
                print(f"       Error: {r.error}")
            for issue in r.data_quality_issues[:3]:  # Show first 3 issues
                print(f"       Issue: {issue}")

    print(f"\nResult: {passed}/{total} tests passed")
    print("=" * 70)

    return passed == total


async def main():
    results = await run_all_tests()
    all_passed = print_summary(results)

    if all_passed:
        print("\nAll E2E tests PASSED!")
        return 0
    else:
        print("\nSome E2E tests FAILED!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
