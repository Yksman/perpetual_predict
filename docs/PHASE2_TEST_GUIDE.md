# Phase 2 기능 검증 테스트 가이드

Phase 2에서 구현된 기능들을 하나씩 검증하기 위한 가이드입니다.

## 사전 준비

### 1. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성하고 다음 내용을 설정합니다:

```bash
# Binance API (선택사항 - 없어도 public API 테스트 가능)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_TESTNET=false

# Whale Alert API (US-25 테스트용)
WHALE_ALERT_API_KEY=your_whale_alert_key
WHALE_ALERT_MIN_VALUE=1000000

# CryptoPanic API (US-26 테스트용)
CRYPTOPANIC_API_KEY=your_cryptopanic_key
CRYPTOPANIC_CURRENCIES=BTC

# Telegram Bot (US-32~36 테스트용)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_ENABLED=true

# Scheduler (US-27~31 테스트용)
SCHEDULER_COLLECTION_INTERVAL=4
SCHEDULER_REPORT_INTERVAL=4
SCHEDULER_RETENTION_DAYS=30

# Database
DATABASE_PATH=data/perpetual_predict.db

# Logging
LOG_LEVEL=DEBUG
```

### 2. 데이터베이스 초기화

```bash
# 기존 DB 삭제 후 새로 시작 (선택사항)
rm -f data/perpetual_predict.db

# 테스트용 데이터 수집
uv run python -m perpetual_predict collect --symbol BTCUSDT --timeframe 4h
```

---

## Priority 1: Data Sources 검증

### US-21: Liquidation Collector

Binance Futures 청산 데이터 수집 기능을 검증합니다.

```python
# tests/manual/test_liquidation.py
import asyncio
from perpetual_predict.collectors.binance.liquidation import LiquidationCollector
from perpetual_predict.storage.database import Database

async def test_liquidation():
    db = Database()
    await db.initialize()

    collector = LiquidationCollector()

    # 최근 청산 데이터 수집
    liquidations = await collector.collect(limit=10)

    print(f"수집된 청산 건수: {len(liquidations)}")
    for liq in liquidations[:3]:
        print(f"  - {liq.side} {liq.original_qty} @ ${liq.price:,.2f} ({liq.timestamp})")

    # DB 저장 테스트
    if liquidations:
        await db.insert_liquidations(liquidations)
        print("✅ DB 저장 완료")

    await db.close()
    await collector.close()

asyncio.run(test_liquidation())
```

**실행:**
```bash
uv run python tests/manual/test_liquidation.py
```

**예상 결과:**
```
수집된 청산 건수: 10
  - SELL 0.05 @ $67,234.50 (2024-01-15 10:30:00)
  - BUY 0.12 @ $67,189.00 (2024-01-15 10:28:30)
  ...
✅ DB 저장 완료
```

---

### US-22, US-23, US-24: WebSocket Streams

실시간 가격 및 거래 스트림을 검증합니다.

```python
# tests/manual/test_websocket.py
import asyncio
from perpetual_predict.collectors.websocket.binance_ws import (
    MarkPriceStream,
    AggTradeStream,
    CombinedStream,
)

async def test_mark_price_stream():
    """Mark Price 스트림 테스트 (5초간)"""
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
    """Aggregate Trade 스트림 테스트 (5초간)"""
    print("\n=== Aggregate Trade Stream 테스트 ===")

    trades = []

    async def on_trade(data):
        trades.append(data)
        side = "SELL" if data['m'] else "BUY"
        print(f"  Trade: {side} {float(data['q']):.4f} @ ${float(data['p']):,.2f}")

    stream = AggTradeStream(symbol="btcusdt", callback=on_trade)
    await stream.connect()

    await asyncio.sleep(5)
    await stream.disconnect()

    print(f"✅ {len(trades)}개 거래 데이터 수신")

async def test_combined_stream():
    """Combined Stream 테스트 (5초간)"""
    print("\n=== Combined Stream 테스트 ===")

    messages = []

    async def on_message(data):
        messages.append(data)
        stream_type = data.get('e', 'unknown')
        print(f"  [{stream_type}] 메시지 수신")

    stream = CombinedStream(
        symbol="btcusdt",
        streams=["markPrice", "aggTrade"],
        callback=on_message
    )
    await stream.connect()

    await asyncio.sleep(5)
    await stream.disconnect()

    print(f"✅ {len(messages)}개 메시지 수신")

async def main():
    await test_mark_price_stream()
    await test_agg_trade_stream()
    await test_combined_stream()

asyncio.run(main())
```

**실행:**
```bash
uv run python tests/manual/test_websocket.py
```

**예상 결과:**
```
=== Mark Price Stream 테스트 ===
  Mark Price: $67,234.50, Funding: 0.000100
  Mark Price: $67,235.00, Funding: 0.000100
  ...
✅ 5개 가격 데이터 수신

=== Aggregate Trade Stream 테스트 ===
  Trade: BUY 0.0500 @ $67,234.50
  Trade: SELL 0.1200 @ $67,233.00
  ...
✅ 150개 거래 데이터 수신
```

---

### US-25: Whale Alert Collector

대규모 암호화폐 거래 알림을 검증합니다.

> ⚠️ **주의**: Whale Alert API 키가 필요합니다. 무료 플랜은 분당 10회 제한이 있습니다.

```python
# tests/manual/test_whale_alert.py
import asyncio
from perpetual_predict.collectors.onchain.whale_alert import WhaleAlertCollector
from perpetual_predict.storage.database import Database

async def test_whale_alert():
    db = Database()
    await db.initialize()

    collector = WhaleAlertCollector()

    if not collector.api_key:
        print("❌ WHALE_ALERT_API_KEY 환경변수가 설정되지 않았습니다")
        return

    print("=== Whale Alert 테스트 ===")

    # 최근 1시간 내 대규모 거래 조회
    transactions = await collector.collect(limit=5)

    print(f"수집된 고래 거래: {len(transactions)}건")
    for tx in transactions:
        print(f"  - {tx.blockchain}: {tx.amount:,.0f} {tx.symbol}")
        print(f"    {tx.from_owner} → {tx.to_owner}")
        print(f"    가치: ${tx.amount_usd:,.0f}")
        print()

    # DB 저장 테스트
    if transactions:
        await db.insert_whale_transactions(transactions)
        print("✅ DB 저장 완료")

    await db.close()
    await collector.close()

asyncio.run(test_whale_alert())
```

**실행:**
```bash
uv run python tests/manual/test_whale_alert.py
```

**예상 결과:**
```
=== Whale Alert 테스트 ===
수집된 고래 거래: 5건
  - bitcoin: 500 BTC
    binance → unknown
    가치: $33,500,000

  - ethereum: 10,000 ETH
    unknown → coinbase
    가치: $25,000,000
...
✅ DB 저장 완료
```

---

### US-26: CryptoPanic News Collector

암호화폐 뉴스 및 감성 분석 데이터를 검증합니다.

> ⚠️ **주의**: CryptoPanic API 키가 필요합니다.

```python
# tests/manual/test_cryptopanic.py
import asyncio
from perpetual_predict.collectors.news.cryptopanic import CryptoPanicCollector
from perpetual_predict.storage.database import Database

async def test_cryptopanic():
    db = Database()
    await db.initialize()

    collector = CryptoPanicCollector()

    if not collector.api_key:
        print("❌ CRYPTOPANIC_API_KEY 환경변수가 설정되지 않았습니다")
        return

    print("=== CryptoPanic News 테스트 ===")

    # 최근 뉴스 조회
    news_items = await collector.collect(limit=5)

    print(f"수집된 뉴스: {len(news_items)}건\n")
    for item in news_items:
        sentiment_emoji = {
            "positive": "🟢",
            "negative": "🔴",
            "neutral": "⚪"
        }.get(item.sentiment, "⚪")

        print(f"{sentiment_emoji} [{item.kind}] {item.title}")
        print(f"   소스: {item.source} | 투표: 👍{item.votes_positive} 👎{item.votes_negative}")
        print(f"   URL: {item.url}")
        print()

    # DB 저장 테스트
    if news_items:
        await db.insert_news_items(news_items)
        print("✅ DB 저장 완료")

    await db.close()
    await collector.close()

asyncio.run(test_cryptopanic())
```

**실행:**
```bash
uv run python tests/manual/test_cryptopanic.py
```

**예상 결과:**
```
=== CryptoPanic News 테스트 ===
수집된 뉴스: 5건

🟢 [news] Bitcoin ETF sees record inflows
   소스: CoinDesk | 투표: 👍45 👎2
   URL: https://...

🔴 [news] SEC delays decision on crypto regulations
   소스: Reuters | 투표: 👍12 👎28
   URL: https://...
...
✅ DB 저장 완료
```

---

## Priority 2: Scheduler 검증

### US-27, US-28: Scheduler Manager

APScheduler 기반 스케줄러 관리자를 검증합니다.

```python
# tests/manual/test_scheduler.py
import asyncio
from perpetual_predict.scheduler.scheduler import SchedulerManager

async def test_scheduler():
    print("=== Scheduler Manager 테스트 ===")

    scheduler = SchedulerManager()

    counter = {"value": 0}

    async def sample_job():
        counter["value"] += 1
        print(f"  Job 실행: #{counter['value']}")

    # 2초마다 실행되는 작업 등록
    scheduler.add_interval_job(
        func=sample_job,
        job_id="test_job",
        seconds=2,
        name="테스트 작업"
    )

    print("등록된 작업:")
    for job in scheduler.get_jobs():
        print(f"  - {job.id}: {job.name}")

    print("\n스케줄러 시작 (10초간 실행)...")
    await scheduler.start()

    await asyncio.sleep(10)

    await scheduler.stop()
    print(f"\n✅ 스케줄러 종료 (총 {counter['value']}회 실행)")

asyncio.run(test_scheduler())
```

**실행:**
```bash
uv run python tests/manual/test_scheduler.py
```

**예상 결과:**
```
=== Scheduler Manager 테스트 ===
등록된 작업:
  - test_job: 테스트 작업

스케줄러 시작 (10초간 실행)...
  Job 실행: #1
  Job 실행: #2
  Job 실행: #3
  Job 실행: #4
  Job 실행: #5

✅ 스케줄러 종료 (총 5회 실행)
```

---

### US-29, US-30: Collection & Report Jobs

데이터 수집 및 리포트 생성 작업을 검증합니다.

```python
# tests/manual/test_jobs.py
import asyncio
from perpetual_predict.storage.database import Database
from perpetual_predict.scheduler.jobs import collection_job, report_job

async def test_jobs():
    db = Database()
    await db.initialize()

    print("=== Collection Job 테스트 ===")
    await collection_job(db)
    print("✅ 데이터 수집 완료\n")

    print("=== Report Job 테스트 ===")
    report_path = await report_job(db, output_dir="reports")
    if report_path:
        print(f"✅ 리포트 생성: {report_path}")
    else:
        print("⚠️ 리포트 생성 실패 (데이터 부족)")

    await db.close()

asyncio.run(test_jobs())
```

**실행:**
```bash
uv run python tests/manual/test_jobs.py
```

**예상 결과:**
```
=== Collection Job 테스트 ===
✅ 데이터 수집 완료

=== Report Job 테스트 ===
✅ 리포트 생성: reports/analysis_20240115_103000.md
```

---

### US-31: Daemon CLI

데몬 모드 CLI를 검증합니다.

```bash
# 도움말 확인
uv run python -m perpetual_predict daemon --help
```

**예상 결과:**
```
usage: perpetual_predict daemon [-h] [--background] [--collection-interval HOURS]
                                [--report-interval HOURS]

options:
  -h, --help            show this help message and exit
  --background          Run in background (not implemented)
  --collection-interval HOURS
                        Data collection interval in hours (default: 4)
  --report-interval HOURS
                        Report generation interval in hours (default: 4)
```

```bash
# 짧은 테스트 실행 (Ctrl+C로 종료)
uv run python -m perpetual_predict daemon --collection-interval 1 --report-interval 1
```

**예상 결과:**
```
Starting daemon with collection_interval=1h, report_interval=1h
Press Ctrl+C to stop...

2024-01-15 10:30:00 - Running collection job...
2024-01-15 10:30:05 - Collection completed
...
```

---

## Priority 3: Telegram Notifications 검증

### US-32, US-33: Telegram Bot Client

Telegram Bot 연결 및 메시지 전송을 검증합니다.

> ⚠️ **사전 준비**:
> 1. [@BotFather](https://t.me/botfather)에서 봇 생성 후 토큰 획득
> 2. 봇과 대화 시작 후 Chat ID 확인 ([@userinfobot](https://t.me/userinfobot) 사용)
> 3. `.env`에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED=true` 설정

```python
# tests/manual/test_telegram.py
import asyncio
from perpetual_predict.notifications.telegram_bot import TelegramBot

async def test_telegram():
    bot = TelegramBot()

    if not bot.is_configured:
        print("❌ Telegram 봇이 설정되지 않았습니다")
        print("   TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 확인하세요")
        return

    print("=== Telegram Bot 테스트 ===")

    # 봇 정보 확인
    bot_info = await bot.get_me()
    if bot_info:
        print(f"✅ 봇 연결 성공: @{bot_info['username']}")
    else:
        print("❌ 봇 연결 실패")
        return

    # 텍스트 메시지 전송
    print("\n메시지 전송 테스트...")
    result = await bot.send_message(
        text="*테스트 메시지*\n\n이것은 Phase 2 기능 검증 테스트입니다.",
        parse_mode="Markdown"
    )

    if result:
        print("✅ 메시지 전송 성공")
    else:
        print("❌ 메시지 전송 실패")

    await bot.close()

asyncio.run(test_telegram())
```

**실행:**
```bash
uv run python tests/manual/test_telegram.py
```

**예상 결과:**
```
=== Telegram Bot 테스트 ===
✅ 봇 연결 성공: @your_bot_name

메시지 전송 테스트...
✅ 메시지 전송 성공
```

---

### US-34: RSI Alert

RSI 극단값 알림을 검증합니다.

```python
# tests/manual/test_rsi_alert.py
import asyncio
from perpetual_predict.notifications.telegram_bot import TelegramBot
from perpetual_predict.notifications.alerts import send_rsi_alert

async def test_rsi_alert():
    bot = TelegramBot()

    if not bot.is_configured:
        print("❌ Telegram 봇이 설정되지 않았습니다")
        return

    print("=== RSI Alert 테스트 ===")

    # 과매수 알림 테스트
    print("과매수 알림 전송...")
    result = await send_rsi_alert(
        bot=bot,
        rsi_value=75.5,
        signal_type="overbought",
        symbol="BTCUSDT"
    )
    print(f"{'✅' if result else '❌'} 과매수 알림")

    await asyncio.sleep(1)

    # 과매도 알림 테스트
    print("과매도 알림 전송...")
    result = await send_rsi_alert(
        bot=bot,
        rsi_value=25.3,
        signal_type="oversold",
        symbol="BTCUSDT"
    )
    print(f"{'✅' if result else '❌'} 과매도 알림")

    await bot.close()

asyncio.run(test_rsi_alert())
```

**실행:**
```bash
uv run python tests/manual/test_rsi_alert.py
```

**예상 결과:**
```
=== RSI Alert 테스트 ===
과매수 알림 전송...
✅ 과매수 알림
과매도 알림 전송...
✅ 과매도 알림
```

**Telegram에서 확인:**
```
🔴 RSI Alert: Overbought

Symbol: BTCUSDT
RSI: 75.50

Price may be due for a correction.
```

---

### US-35: Support/Resistance Alert

지지/저항선 알림을 검증합니다.

```python
# tests/manual/test_sr_alert.py
import asyncio
from perpetual_predict.notifications.telegram_bot import TelegramBot
from perpetual_predict.notifications.alerts import send_sr_alert

async def test_sr_alert():
    bot = TelegramBot()

    if not bot.is_configured:
        print("❌ Telegram 봇이 설정되지 않았습니다")
        return

    print("=== Support/Resistance Alert 테스트 ===")

    # 지지선 알림 테스트
    print("지지선 알림 전송...")
    result = await send_sr_alert(
        bot=bot,
        price=67150.00,
        level=67000.00,
        level_type="support",
        symbol="BTCUSDT"
    )
    print(f"{'✅' if result else '❌'} 지지선 알림")

    await asyncio.sleep(1)

    # 저항선 알림 테스트
    print("저항선 알림 전송...")
    result = await send_sr_alert(
        bot=bot,
        price=69850.00,
        level=70000.00,
        level_type="resistance",
        symbol="BTCUSDT"
    )
    print(f"{'✅' if result else '❌'} 저항선 알림")

    await bot.close()

asyncio.run(test_sr_alert())
```

**실행:**
```bash
uv run python tests/manual/test_sr_alert.py
```

**예상 결과:**
```
=== Support/Resistance Alert 테스트 ===
지지선 알림 전송...
✅ 지지선 알림
저항선 알림 전송...
✅ 저항선 알림
```

---

### US-36: Status Message

시스템 상태 메시지를 검증합니다.

```python
# tests/manual/test_status.py
import asyncio
from perpetual_predict.notifications.telegram_bot import TelegramBot
from perpetual_predict.notifications.alerts import send_status_message
from perpetual_predict.storage.database import Database

async def test_status():
    bot = TelegramBot()
    db = Database()

    if not bot.is_configured:
        print("❌ Telegram 봇이 설정되지 않았습니다")
        return

    await db.initialize()

    print("=== Status Message 테스트 ===")

    result = await send_status_message(
        bot=bot,
        database=db,
        symbol="BTCUSDT"
    )

    print(f"{'✅' if result else '❌'} 상태 메시지 전송")

    await db.close()
    await bot.close()

asyncio.run(test_status())
```

**실행:**
```bash
uv run python tests/manual/test_status.py
```

**예상 결과:**
```
=== Status Message 테스트 ===
✅ 상태 메시지 전송
```

**Telegram에서 확인:**
```
📊 Perpetual Predict Status

Symbol: BTCUSDT

Latest Data:
• Price: $67,234.50
• Last candle: 2024-01-15 10:00
• Funding rate: 0.0100%

Recent Jobs:
• ✅ collection_job (10:30)
• ✅ report_job (10:30)
```

---

## 전체 기능 통합 테스트

모든 기능을 한 번에 테스트합니다.

```python
# tests/manual/test_all.py
import asyncio
import sys

async def run_all_tests():
    tests = [
        ("US-21: Liquidation", "test_liquidation"),
        ("US-22~24: WebSocket", "test_websocket"),
        ("US-25: Whale Alert", "test_whale_alert"),
        ("US-26: CryptoPanic", "test_cryptopanic"),
        ("US-27~28: Scheduler", "test_scheduler"),
        ("US-29~30: Jobs", "test_jobs"),
        ("US-32~33: Telegram", "test_telegram"),
        ("US-34: RSI Alert", "test_rsi_alert"),
        ("US-35: S/R Alert", "test_sr_alert"),
        ("US-36: Status", "test_status"),
    ]

    print("=" * 50)
    print("Phase 2 전체 기능 테스트")
    print("=" * 50)

    results = []
    for name, module in tests:
        print(f"\n▶ {name}")
        try:
            # 각 테스트 모듈 동적 임포트 및 실행
            mod = __import__(module)
            if hasattr(mod, 'main'):
                await mod.main()
            results.append((name, "✅"))
        except Exception as e:
            results.append((name, f"❌ {e}"))

    print("\n" + "=" * 50)
    print("테스트 결과 요약")
    print("=" * 50)
    for name, status in results:
        print(f"  {status} {name}")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
```

---

## 문제 해결 가이드

### 1. API 키 관련 오류

```
❌ WHALE_ALERT_API_KEY 환경변수가 설정되지 않았습니다
```

**해결:** `.env` 파일에 해당 API 키를 추가하세요.

### 2. WebSocket 연결 실패

```
Connection refused / Timeout
```

**해결:**
- 네트워크 연결 확인
- VPN 사용 시 비활성화
- 방화벽 설정 확인

### 3. Telegram 메시지 전송 실패

```
❌ 메시지 전송 실패
```

**해결:**
1. Bot Token이 올바른지 확인
2. Chat ID가 올바른지 확인
3. 봇과 먼저 대화를 시작했는지 확인
4. `TELEGRAM_ENABLED=true` 설정 확인

### 4. 데이터베이스 오류

```
sqlite3.OperationalError: no such table
```

**해결:**
```bash
# DB 재초기화
rm -f data/perpetual_predict.db
uv run python -m perpetual_predict collect
```

---

## 체크리스트

| Feature | 테스트 | 결과 |
|---------|--------|------|
| US-21 Liquidation Collector | `test_liquidation.py` | ☐ |
| US-22 WebSocket Base | `test_websocket.py` | ☐ |
| US-23 Price Stream | `test_websocket.py` | ☐ |
| US-24 Trade Stream | `test_websocket.py` | ☐ |
| US-25 Whale Alert | `test_whale_alert.py` | ☐ |
| US-26 CryptoPanic | `test_cryptopanic.py` | ☐ |
| US-27 Scheduler Config | `test_scheduler.py` | ☐ |
| US-28 APScheduler Manager | `test_scheduler.py` | ☐ |
| US-29 Collection Job | `test_jobs.py` | ☐ |
| US-30 Report Job | `test_jobs.py` | ☐ |
| US-31 Daemon CLI | CLI 직접 실행 | ☐ |
| US-32 Telegram Config | `test_telegram.py` | ☐ |
| US-33 Telegram Client | `test_telegram.py` | ☐ |
| US-34 RSI Alert | `test_rsi_alert.py` | ☐ |
| US-35 S/R Alert | `test_sr_alert.py` | ☐ |
| US-36 Status Message | `test_status.py` | ☐ |
