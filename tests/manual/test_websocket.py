"""US-22, US-23, US-24: WebSocket Streams 테스트."""

import asyncio

from perpetual_predict.collectors.websocket.binance_ws import (
    AggTradeStream,
    CombinedStream,
    MarkPriceStream,
)


async def test_mark_price_stream():
    """Mark Price 스트림 테스트 (5초간)."""
    print("=== Mark Price Stream 테스트 ===")

    prices = []

    async def on_price(data):
        prices.append(data)
        print(f"  Mark Price: ${float(data['p']):,.2f}, Funding: {float(data['r']):.6f}")

    stream = MarkPriceStream(symbol="btcusdt", callback=on_price)
    await stream.connect()

    await asyncio.sleep(5)
    await stream.disconnect()

    print(f"✅ {len(prices)}개 가격 데이터 수신")


async def test_agg_trade_stream():
    """Aggregate Trade 스트림 테스트 (5초간)."""
    print("\n=== Aggregate Trade Stream 테스트 ===")

    trades = []

    async def on_trade(data):
        trades.append(data)
        side = "SELL" if data["m"] else "BUY"
        print(f"  Trade: {side} {float(data['q']):.4f} @ ${float(data['p']):,.2f}")

    stream = AggTradeStream(symbol="btcusdt", callback=on_trade)
    await stream.connect()

    await asyncio.sleep(5)
    await stream.disconnect()

    print(f"✅ {len(trades)}개 거래 데이터 수신")


async def test_combined_stream():
    """Combined Stream 테스트 (5초간)."""
    print("\n=== Combined Stream 테스트 ===")

    messages = []

    async def on_message(data):
        messages.append(data)
        stream_type = data.get("e", "unknown")
        print(f"  [{stream_type}] 메시지 수신")

    stream = CombinedStream(
        symbol="btcusdt", streams=["markPrice", "aggTrade"], callback=on_message
    )
    await stream.connect()

    await asyncio.sleep(5)
    await stream.disconnect()

    print(f"✅ {len(messages)}개 메시지 수신")


async def main():
    await test_mark_price_stream()
    await test_agg_trade_stream()
    await test_combined_stream()


if __name__ == "__main__":
    asyncio.run(main())
