# 파이프라인 아키텍처 평가 보고서

**평가일:** 2026-03-22
**대상:** 데이터 수집 → 에이전트 분석 → 디스코드 알림 전체 파이프라인

---

## 1. 파이프라인 개요

```
[Data Collection]  →  [SQLite Storage]  →  [Technical Analysis]
        ↓                                        ↓
  5개 데이터 소스              [Market Context Builder]
  - OHLCV (4H)                        ↓
  - Funding Rate              [Claude Agent (LLM)]
  - Open Interest                     ↓
  - Long/Short Ratio          [Prediction 저장]
  - Fear & Greed Index                ↓
                              [Prediction Evaluation]
                                      ↓
                              [Discord 알림]
```

**스케줄링:** APScheduler → 4시간 주기 (00:01, 04:01, 08:01, 12:01, 16:01, 20:01 UTC)
**실행 순서:** Evaluate → Collect → Predict (full_cycle_job)

---

## 2. 종합 평가

| 구성요소 | 완성도 | 견고성 | 등급 |
|----------|--------|--------|------|
| 데이터 수집 (Collectors) | 100% | 70% | **C+** |
| 저장소 (Storage/DB) | 100% | 75% | **B-** |
| 기술적 분석 (Analyzers) | 100% | 80% | **B** |
| LLM 에이전트 (Claude) | 100% | 85% | **B+** |
| 예측 평가 (Evaluation) | 100% | 75% | **B-** |
| 스케줄러 (Scheduler) | 100% | 80% | **B** |
| 디스코드 알림 | 100% | 85% | **B+** |
| 테스트 커버리지 | 5% | - | **F** |
| **전체** | **MVP 완성** | **~78%** | **C+** |

---

## 3. 구조적 결함 (Structural Defects)

### 3.1 [CRITICAL] 테스트 커버리지 사실상 부재

- **pytest 테스트 파일:** 1개 (`test_scheduler_alerts.py`, 199줄)
- **소스 코드:** 51개 파일, ~4,883줄
- **추정 커버리지:** < 5%
- **테스트 없는 핵심 모듈:**
  - `storage/database.py` (778줄) — 전체 데이터 영속성
  - `collectors/binance/client.py` — API 클라이언트, 서명, 에러 처리
  - `analyzers/technical/*` — 모든 기술적 지표 계산
  - `llm/agent/runner.py` — Claude 에이전트 실행
  - `llm/context/builder.py` — 시장 컨텍스트 생성
  - `llm/evaluation/evaluator.py` — 예측 평가
  - `scheduler/jobs.py` (425줄) — 작업 정의 및 실행
  - `cli/*` — 모든 CLI 진입점

**영향:** 리팩토링, 의존성 업그레이드, 버그 수정 시 회귀 테스트 불가. 프로덕션 운영 중 사일런트 실패 위험.

### 3.2 [HIGH] 트랜잭션 관리 부재

**위치:** `storage/database.py`

```python
# 현재: 각 insert마다 개별 commit
await self.db.execute("INSERT OR REPLACE INTO candles ...", params)
await self.db.commit()
```

- 수집 작업에서 수백 개의 레코드를 개별 commit → 성능 저하
- 수집 중간에 실패하면 부분 데이터만 저장 → 데이터 정합성 훼손
- **개선:** 수집 단위별 batch transaction 필요

### 3.3 [HIGH] datetime 비일관성

**위치:** `storage/database.py:717`

```python
# 문제: deprecated 메서드 사용
now = datetime.utcnow()  # timezone-naive

# 다른 모듈에서는:
datetime.now(timezone.utc)  # timezone-aware
```

- timezone-naive와 timezone-aware datetime 혼용
- SQLite 비교 시 예상치 못한 결과 가능
- Python 3.12에서 `utcnow()` deprecation 경고 발생

### 3.4 [MEDIUM] 순환 의존성 위험

```
scheduler/jobs.py → reporters/data_integrity.py → storage/database.py
notifications/scheduler_alerts.py → (lazy import) → reporters/discord_report.py
```

- `scheduler_alerts.py`에서 lazy import로 우회 중 (line 134-136)
- 현재 동작하지만, 모듈 구조 변경 시 깨지기 쉬움

### 3.5 [MEDIUM] conftest.py 및 테스트 fixture 부재

- 공통 fixture (mock DB, mock API client, sample data) 없음
- pytest-asyncio 설정 없음
- 테스트 환경 분리 안됨 (실제 DB 접근 가능성)

---

## 4. 기능적 결함 (Functional Defects)

### 4.1 [CRITICAL] Fear & Greed Index — 단일 장애점

**위치:** `collectors/sentiment/fear_greed.py`

- 외부 API (alternative.me)에 의존하지만 **retry 로직 없음**
- API 장애 시 전체 수집 작업 영향
- `cli/collect.py`에서 try-finally로 감싸지만, 실패 시 해당 데이터 누락
- 다른 Binance 수집기들은 `BinanceClient`의 에러 처리 공유하지만, FGI는 독립적

**개선:** `utils/retry.py`의 retry 데코레이터 적용 필요. 또는 선택적(optional) 수집으로 분리.

### 4.2 [HIGH] 리포트 생성 시 지표 검증 부족

**위치:** `cli/report.py:124-151`

```python
# 위험: candle 수가 충분하지 않으면 NaN/crash
sma_20 = trend.calculate_sma(df, period=20)  # 최소 20개 candle 필요
current_sma20 = sma_20.iloc[-1]               # NaN일 수 있음
```

- 20개 미만의 candle로 SMA_20 계산 시 NaN 반환
- `.iloc[-1]`에서 NaN 값이 리포트에 그대로 들어감
- SMA_200은 200개 candle 필요 — 7일(42개 4H candle) 수집으로는 불충분

### 4.3 [HIGH] Context Builder의 무음 실패

**위치:** `llm/context/builder.py`

- `_safe_get()` 메서드가 누락된 지표를 기본값(0)으로 대체
- ATR=0, ADX=0 등은 "변동성 없음", "추세 없음"으로 해석 → **잘못된 분석 유도**
- 에이전트에게 데이터 부족/불완전 상태를 알리지 않음

**개선:** 기본값 대신 `null`/`N/A` 표시, 또는 프롬프트에 데이터 가용성 명시.

### 4.4 [HIGH] 데이터 신선도 검증 없음

- 수집된 데이터가 실제로 최신인지 확인하지 않음
- Binance API가 캐싱된 오래된 데이터를 반환해도 그대로 저장
- 4H 경계에 정렬되지 않은 candle 데이터 가능성
- `data_integrity.py`에 gap 검사 있지만, 수집 시점이 아닌 리포트 시점에만 실행

### 4.5 [MEDIUM] 미평가 예측의 TTL 없음

**위치:** `llm/evaluation/evaluator.py`

- `is_correct IS NULL`인 예측이 무한히 pending 상태로 남을 수 있음
- 데이터 수집 누락으로 target candle이 없으면 영원히 평가 불가
- 오래된 pending 예측이 누적되면 매 사이클마다 불필요한 조회

**개선:** 일정 시간(예: 48시간) 경과 후 `EXPIRED`로 마킹하는 로직 필요.

### 4.6 [MEDIUM] Claude Agent 타임아웃 하드코딩

**위치:** `llm/agent/runner.py`

```python
timeout = 120  # seconds, not configurable
```

- 네트워크 상태, 모델 부하에 따라 120초 초과 가능
- Cloud Run의 request timeout과 충돌 가능
- 설정(`SchedulerConfig` 또는 별도)으로 외부화 필요

### 4.7 [MEDIUM] 디스코드 알림 전송 확인 없음

- 웹훅 전송 후 응답 상태만 확인, 실제 메시지 도달 검증 안됨
- 전송 이력(audit log) 미저장
- Rate limit 초과 시 retry는 있지만, 실패 시 데이터 유실

### 4.8 [LOW] Open Interest 현재값 USD 누락

**위치:** `collectors/binance/open_interest.py`

- 현재 OI 엔드포인트: `sumOpenInterest`만 제공, USD 값 없음 → `0.0`으로 설정
- 히스토리 OI에는 USD 값 있음 → 데이터 불일치
- Context Builder에서 OI 변화율 계산 시 0.0이 포함되면 왜곡

---

## 5. 아키텍처 설계 평가

### 5.1 잘된 점

1. **Async-first 설계:** 모든 I/O 작업이 `asyncio` + `aiohttp` 기반으로 일관됨
2. **관심사 분리:** collectors / analyzers / storage / notifications가 명확히 분리
3. **LLM 폴백 전략:** JSON 파싱 실패 시 마크다운 추출 → 키워드 기반 추출로 3단계 폴백
4. **Graceful Shutdown:** SIGTERM/SIGINT 핸들러로 스케줄러 안전 종료
5. **Health Tracking:** 작업별 성공/실패 카운터와 상태 파일 기록
6. **Data Integrity Reporter:** 수집 후 데이터 품질 자동 검사 (gap, duplicate 탐지)

### 5.2 설계 우려사항

1. **단일 SQLite 파일:** 동시 쓰기 제한, 데이터 증가 시 성능 저하 예상. 현재 MVP에는 적절하나 확장성 한계.
2. **동기화 경계:** `asyncio.run()`으로 CLI에서 async 코드 실행 — 중첩 이벤트 루프 문제 가능성 (Jupyter 등에서).
3. **설정 불변성:** 런타임 설정 변경 불가 (`reload_settings()` 있으나 실제 사용 안됨).
4. **Out-of-scope 설정 클래스 존재:** `WebSocketConfig`, `WhaleAlertConfig`, `CryptoPanicConfig` 등 사용하지 않는 설정이 코드에 포함 → 혼란 유발.

---

## 6. 데이터 흐름 Edge Case

| 시나리오 | 현재 동작 | 위험도 |
|----------|----------|--------|
| Binance API 점검 중 수집 | BinanceAPIError → 전체 수집 실패 | HIGH |
| 4H candle < 20개로 분석 | NaN 지표 → 잘못된 컨텍스트 | HIGH |
| Claude CLI 미설치 상태 | FileNotFoundError → 예측 실패 | MEDIUM |
| Discord 웹훅 URL 미설정 | 경고 로그 후 계속 진행 (정상) | LOW |
| 동시에 두 스케줄러 인스턴스 | SQLite 잠금 충돌 | HIGH |
| 자정에 날짜 변경 중 수집 | 경계 candle 누락 가능 | LOW |

---

## 7. 우선순위별 개선 권고

### P0 (즉시)
1. **핵심 모듈 단위 테스트 추가** — database.py, collectors, analyzers 최소 커버리지 확보
2. **Fear & Greed 수집기에 retry 로직 추가** — `@with_retry` 데코레이터 적용
3. **지표 계산 전 최소 candle 수 검증** — 부족 시 해당 지표 스킵

### P1 (1주 내)
4. **DB 트랜잭션 batch 처리** — 수집 단위별 단일 트랜잭션
5. **`datetime.utcnow()` → `datetime.now(timezone.utc)` 전환**
6. **Context Builder에서 데이터 가용성 명시** — 누락 지표를 프롬프트에 표시
7. **미평가 예측 TTL 구현** — 48시간 후 EXPIRED 처리

### P2 (2주 내)
8. **Claude Agent 타임아웃 설정 외부화**
9. **OI 현재값 USD 계산** — mark_price × sumOpenInterest로 추정
10. **디스코드 전송 이력 로깅**
11. **미사용 설정 클래스 제거** (WebSocket, WhaleAlert, CryptoPanic)

---

## 8. 결론

파이프라인은 **MVP로서 기능적으로 완성**되어 있으며, 데이터 수집부터 AI 분석, 디스코드 알림까지의 전체 흐름이 동작합니다. Async-first 설계, 관심사 분리, LLM 폴백 전략 등 아키텍처적으로 좋은 결정이 다수 포함되어 있습니다.

그러나 **프로덕션 운영에는 아직 부족**합니다. 핵심 문제는:

1. **테스트 커버리지 5% 미만** — 어떤 변경도 안전하게 할 수 없는 상태
2. **데이터 정합성 보장 부재** — 트랜잭션 없는 개별 commit, 신선도 검증 없음
3. **외부 의존성 취약점** — FGI 단일 장애점, 지표 계산 무음 실패
4. **무음 데이터 왜곡** — 기본값 0이 "데이터 없음"이 아닌 "값이 0"으로 해석됨

**전체 등급: C+** — 기능은 완성되었으나 견고성과 테스트가 크게 부족한 상태.
