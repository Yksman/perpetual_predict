# Data Collector Manual Testing Guide

각 데이터 수집기를 수동으로 실행하고 테스트하는 방법을 설명합니다.

## 사전 준비

```bash
# 1. 가상환경 활성화 및 의존성 설치
uv sync

# 2. 환경변수 설정 (.env 파일)
cp .env.example .env
```

### 환경변수 설정 (선택사항)

Binance 공개 API는 키 없이 사용 가능합니다.

```env
# Binance (선택사항 - 공개 API는 키 없이 사용 가능)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
```

---

## 1. OHLCV Collector (캔들 데이터)

BTCUSDT 4시간봉 캔들 데이터를 수집합니다.

### 실행 코드

```python
import asyncio
from perpetual_predict.collectors.binance.market_data import OHLCVCollector

async def main():
    collector = OHLCVCollector(symbol="BTCUSDT", timeframe="4h")
    try:
        # 최근 10개 캔들 수집
        candles = await collector.collect(limit=10)

        print(f"수집된 캔들 수: {len(candles)}")
        for candle in candles[:3]:  # 최근 3개만 출력
            print(f"""
시간: {candle.open_time}
시가: {candle.open:,.2f}
고가: {candle.high:,.2f}
저가: {candle.low:,.2f}
종가: {candle.close:,.2f}
거래량: {candle.volume:,.4f}
---""")
    finally:
        await collector.close()

asyncio.run(main())
```

### 예상 출력

```
수집된 캔들 수: 10

시간: 2024-01-15 12:00:00+00:00
시가: 42,500.00
고가: 43,200.00
저가: 42,300.00
종가: 42,900.00
거래량: 1,234.5678
---
```

---

## 2. Long/Short Ratio Collector (롱숏 비율)

롱/숏 포지션 비율 데이터를 수집합니다.

### 실행 코드

```python
import asyncio
from perpetual_predict.collectors.binance.market_data import LongShortRatioCollector

async def main():
    collector = LongShortRatioCollector(symbol="BTCUSDT", period="4h")
    try:
        # 최근 10개 데이터 수집
        ratios = await collector.collect(limit=10)

        print(f"수집된 데이터 수: {len(ratios)}")
        for ratio in ratios[:3]:
            print(f"""
시간: {ratio.timestamp}
롱 비율: {ratio.long_ratio:.4f} ({ratio.long_ratio*100:.2f}%)
숏 비율: {ratio.short_ratio:.4f} ({ratio.short_ratio*100:.2f}%)
롱/숏 비율: {ratio.long_short_ratio:.4f}
---""")
    finally:
        await collector.close()

asyncio.run(main())
```

### 예상 출력

```
수집된 데이터 수: 10

시간: 2024-01-15 12:00:00+00:00
롱 비율: 0.5234 (52.34%)
숏 비율: 0.4766 (47.66%)
롱/숏 비율: 1.0982
---
```

---

## 3. Funding Rate Collector (펀딩비)

무기한 선물 펀딩비 데이터를 수집합니다.

### 실행 코드

```python
import asyncio
from perpetual_predict.collectors.binance.funding import FundingRateCollector

async def main():
    collector = FundingRateCollector(symbol="BTCUSDT")
    try:
        # 현재 펀딩비 조회
        current = await collector.collect_current()
        if current:
            print(f"""
=== 현재 펀딩비 ===
심볼: {current.symbol}
펀딩비: {current.funding_rate:.6f} ({current.funding_rate*100:.4f}%)
마크 가격: {current.mark_price:,.2f}
펀딩 시간: {current.funding_time}
""")

        # 최근 10개 펀딩비 히스토리
        rates = await collector.collect(limit=10)
        print(f"\n=== 펀딩비 히스토리 ({len(rates)}개) ===")
        for rate in rates[:5]:
            print(f"  {rate.funding_time}: {rate.funding_rate:.6f}")

    finally:
        await collector.close()

asyncio.run(main())
```

### 예상 출력

```
=== 현재 펀딩비 ===
심볼: BTCUSDT
펀딩비: 0.000100 (0.0100%)
마크 가격: 42,500.00
펀딩 시간: 2024-01-15 16:00:00+00:00

=== 펀딩비 히스토리 (10개) ===
  2024-01-15 16:00:00+00:00: 0.000100
  2024-01-15 08:00:00+00:00: 0.000085
  ...
```

---

## 4. Open Interest Collector (미결제약정)

미결제약정(Open Interest) 데이터를 수집합니다.

### 실행 코드

```python
import asyncio
from perpetual_predict.collectors.binance.open_interest import OpenInterestCollector

async def main():
    collector = OpenInterestCollector(symbol="BTCUSDT", period="4h")
    try:
        # 현재 미결제약정
        current = await collector.collect_current()
        print(f"""
=== 현재 미결제약정 ===
심볼: {current.symbol}
OI (BTC): {current.open_interest:,.4f}
조회 시간: {current.timestamp}
""")

        # 히스토리 데이터
        ois = await collector.collect(limit=10)
        print(f"\n=== OI 히스토리 ({len(ois)}개) ===")
        for oi in ois[:5]:
            print(f"  {oi.timestamp}: {oi.open_interest:,.4f} BTC (${oi.open_interest_value:,.0f})")

    finally:
        await collector.close()

asyncio.run(main())
```

### 예상 출력

```
=== 현재 미결제약정 ===
심볼: BTCUSDT
OI (BTC): 245,678.1234
조회 시간: 2024-01-15 12:30:00+00:00

=== OI 히스토리 (10개) ===
  2024-01-15 12:00:00+00:00: 245,000.0000 BTC ($10,412,500,000)
  ...
```

---

## 5. Fear & Greed Index Collector (공포/탐욕 지수)

Alternative.me의 공포/탐욕 지수를 수집합니다. (API 키 불필요)

### 실행 코드

```python
import asyncio
from perpetual_predict.collectors.sentiment.fear_greed import FearGreedCollector

async def main():
    collector = FearGreedCollector()
    try:
        # 현재 지수
        current = await collector.collect_current()
        if current:
            print(f"""
=== Fear & Greed Index ===
값: {current.value}
분류: {current.classification}
시간: {current.timestamp}
""")

        # 최근 7일 히스토리
        history = await collector.collect(limit=7)
        print("\n=== 7일 히스토리 ===")
        for fgi in history:
            print(f"  {fgi.timestamp.date()}: {fgi.value} ({fgi.classification})")

    finally:
        await collector.close()

asyncio.run(main())
```

### 예상 출력

```
=== Fear & Greed Index ===
값: 72
분류: Greed
시간: 2024-01-15 00:00:00+00:00

=== 7일 히스토리 ===
  2024-01-15: 72 (Greed)
  2024-01-14: 68 (Greed)
  2024-01-13: 65 (Greed)
  ...
```

---

## 빠른 테스트 스크립트

모든 collector를 한번에 테스트하는 스크립트:

```bash
python scripts/test_collectors.py
```

---

## 트러블슈팅

### 연결 오류

```
aiohttp.ClientConnectorError: Cannot connect to host
```

- 네트워크 연결 확인
- VPN 사용 시 Binance IP 차단 여부 확인

### Rate Limit

```
HTTP 429 Too Many Requests
```

- 요청 간격을 늘리세요 (retry 로직이 자동으로 처리함)
- limit 파라미터를 줄여 요청 횟수 감소

### Import 오류

```
ModuleNotFoundError: No module named 'perpetual_predict'
```

```bash
# 개발 모드로 패키지 설치
pip install -e .
# 또는
uv sync
```
