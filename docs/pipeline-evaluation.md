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
| 기술적 분석 (Analyzers) | 100% | 30% | **F** |
| LLM 에이전트 (Claude) | 100% | 40% | **D** |
| 예측 평가 (Evaluation) | 100% | 75% | **B-** |
| 스케줄러 (Scheduler) | 100% | 80% | **B** |
| 디스코드 알림 | 100% | 85% | **B+** |
| **전체** | **MVP 완성** | **~60%** | **D+** |

---

## 3. [CRITICAL] 에이전트가 동작하지 않는 근본 원인

### 3.1 지표 컬럼명 불일치 — 에이전트에 가짜 데이터 전달

**검증 결과 (실제 pandas-ta 출력 vs builder.py 기대값):**

```
pandas-ta 실제 컬럼명          builder.py가 찾는 컬럼명      일치?
─────────────────────────────────────────────────────────────────
ATRr_14                        ATRr_14                        ✗ (아래 참고)
BBL_20_2.0_2.0                 BBL_20_2.0                     ✗
BBM_20_2.0_2.0                 BBM_20_2.0                     ✗
BBU_20_2.0_2.0                 BBU_20_2.0                     ✗
MACD_12_26_9                   MACD_12_26_9                   ✓
MACDh_12_26_9                  MACDh_12_26_9                  ✓
MACDs_12_26_9                  MACDs_12_26_9                  ✓
ADX_14                         ADX_14                         ✓
RSI_14                         RSI_14                         ✓
STOCHRSIk_14_14_3_3            STOCHRSIk_14_14_3_3            ✓
STOCHRSId_14_14_3_3            STOCHRSId_14_14_3_3            ✓
```

**결함 1: ATR 컬럼명 덮어쓰기**

`volatility.py:81`에서 pandas-ta가 반환한 `ATRr_14`를 `ATR_14`로 **이름을 바꿔서** 저장:

```python
# volatility.py:81 — 컬럼명을 강제로 변경
result[f"ATR_{period}"] = atr   # ATRr_14 → ATR_14로 저장
```

`builder.py:239`에서는 원래 pandas-ta 이름으로 조회:

```python
atr=self._safe_get(latest, "ATRr_14", 0),  # ATR_14를 찾아야 하는데 ATRr_14를 찾음
```

**결과:** ATR은 항상 fallback 값 `0` → 에이전트에게 "**변동성 = 0**"으로 전달

**결함 2: Bollinger Bands 컬럼명 이중 접미사**

pandas-ta `bbands()`가 `BBL_20_2.0_2.0`을 반환하지만 builder는 `BBL_20_2.0`을 기대:

```python
# volatility.py:74 — identity transform (아무것도 안 함)
new_col_name = col.replace(f"_{period}", f"_{period}")  # 같은 걸로 교체 = 변경 없음
# 실제 컬럼: BBL_20_2.0_2.0 그대로 저장

# builder.py:240-242 — 존재하지 않는 컬럼 조회
bb_upper=self._safe_get(latest, "BBU_20_2.0", latest["close"] * 1.02),
bb_middle=self._safe_get(latest, "BBM_20_2.0", latest["close"]),
bb_lower=self._safe_get(latest, "BBL_20_2.0", latest["close"] * 0.98),
```

**결과:** BB는 항상 fallback → Upper = 가격×1.02, Middle = 현재가, Lower = 가격×0.98 (가짜 2% 밴드)

**결함 3: SMA_200 물리적 불가능**

builder는 `lookback_candles=100`으로 DB에서 100개 candle만 가져옴.
SMA_200은 200개 candle이 필요하므로 항상 NaN → fallback `latest["close"]` (현재가)

```python
sma_200=self._safe_get(latest, "SMA_200", latest["close"]),
# 결과: SMA 200 = 현재가 → "가격이 SMA 200 위/아래"가 무의미해짐
```

#### 에이전트가 실제로 받는 데이터 vs 실제 시장 데이터

| 지표 | 에이전트가 받는 값 | 실제 의미 | 심각도 |
|------|-------------------|----------|--------|
| ATR (14) | **$0.00 (0.00% of price)** | "변동성 완전히 없음" | CRITICAL |
| BB Upper | **현재가 × 1.02** | 가짜 2% 밴드 | CRITICAL |
| BB Middle | **현재가 그대로** | 이동평균 아님 | CRITICAL |
| BB Lower | **현재가 × 0.98** | 가짜 2% 밴드 | CRITICAL |
| BB Position | **항상 50%** | 밴드 중앙 | HIGH |
| SMA 200 | **현재가 그대로** | 이동평균 아님 | HIGH |

**6개 지표 중 5개가 가짜 데이터.** 에이전트의 분석은 근본적으로 왜곡된 입력으로 수행됨.

---

### 3.2 프롬프트에 구조화된 출력 지시 없음

**위치:** `llm/context/builder.py:157`

```python
prompt = f"""...
Based on this analysis, predict the direction of the NEXT {self.timeframe} candle."""
```

프롬프트는 "다음 캔들 방향을 예측하라"는 한 줄로 끝남. `--json-schema`가 출력 형식을 강제하지만:

- 프롬프트에 `direction`, `confidence`, `reasoning`, `key_factors` 각 필드에 대한 설명 없음
- confidence 범위(0.0-1.0)에 대한 가이드 없음
- key_factors에 몇 개를 넣어야 하는지 없음
- 분석의 프레임워크(기술적 분석 → 심리 → 결론)가 없음

**결과:** 에이전트가 스키마에 맞는 JSON은 만들지만, **분석 품질이 프롬프트에 의존하지 않고 모델의 자체 판단에만 의존** → 일관성 없음.

### 3.3 `--json-schema` 플래그가 market_context 프롬프트와 충돌 가능

**위치:** `llm/agent/runner.py:81-87`

```python
cmd = [
    "claude",
    "-p",
    "--output-format", "json",
    "--json-schema", PREDICTION_SCHEMA,
    market_context,  # 이것이 프롬프트
]
```

`market_context`는 수천 자의 마크다운 텍스트. CLI 인자로 전달되어:
- OS 인자 길이 제한에 걸릴 수 있음 (일부 환경에서 ~128KB)
- `$67,234.50` 같은 가격 표기의 `$` 문자가 shell 변수로 해석될 수 있음 (subprocess.run() list 모드에서는 안전하나 edge case 존재)

---

## 4. 데이터 수집 → 에이전트 활용 구조 평가

### 4.1 수집된 데이터가 에이전트에 도달하는 경로

```
[DB에서 100개 candle 조회]
        ↓
[pandas DataFrame 변환] → _candles_to_df()
        ↓                  open, high, low, close, volume만 추출
[기술 지표 계산]         → add_trend/momentum/volatility_indicators()
        ↓                  ※ 여기서 컬럼명 불일치 발생
[최신 row에서 값 추출]   → _safe_get() with fallback defaults
        ↓                  ※ 여기서 가짜 데이터 주입
[MarketContext 생성]     → 50+ 필드의 dataclass
        ↓
[format_prompt()]        → 마크다운 텍스트로 변환
        ↓
[Claude CLI에 전달]      → subprocess로 실행
```

### 4.2 데이터 손실 지점

| 단계 | 손실 | 영향 |
|------|------|------|
| DB → DataFrame | `quote_volume`, `trades`, `taker_buy_base`, `taker_buy_quote` 누락 | 거래량 분석 불완전 |
| DataFrame → 지표 | ATR, BB 컬럼명 불일치 | 5개 지표 가짜 데이터 |
| 지표 → MarketContext | `_safe_get` fallback | 에이전트 왜곡 |
| MarketContext → Prompt | Support/Resistance 미포함 | 핵심 분석 누락 |
| Prompt → CLI | 단일 행 지시문 | 분석 프레임워크 없음 |

### 4.3 Support/Resistance가 완전히 누락됨

`analyzers/technical/support_resistance.py`가 구현되어 있지만:
- `builder.py`에서 **호출하지 않음**
- `MarketContext` dataclass에 S/R 필드 **없음**
- `format_prompt()`에 S/R 섹션 **없음**

선물 거래에서 지지/저항선은 핵심 지표인데 에이전트에 전달되지 않음.

### 4.4 Volume 분석기 미활용

`analyzers/technical/volume.py`에 OBV, VWAP가 구현되어 있지만:
- `builder.py`에서 `add_volume_indicators()` 호출 안 함
- MarketContext에 해당 필드 없음
- 거래량 정보는 24H 합산 volume만 전달

---

## 5. 기타 구조적/기능적 결함

### 5.1 [HIGH] 트랜잭션 관리 부재

**위치:** `storage/database.py`
- 각 insert마다 개별 commit → 수집 중 실패 시 부분 데이터만 저장

### 5.2 [HIGH] datetime 비일관성

**위치:** `storage/database.py` — `datetime.utcnow()` (deprecated, naive) vs `datetime.now(timezone.utc)` (aware) 혼용

### 5.3 [HIGH] Fear & Greed Index 단일 장애점

외부 API (alternative.me)에 retry 로직 없음. 장애 시 해당 데이터 누락.

### 5.4 [MEDIUM] 미평가 예측의 TTL 없음

`is_correct IS NULL`인 예측이 무한히 pending 상태로 남을 수 있음.

### 5.5 [MEDIUM] Claude Agent 타임아웃 하드코딩 (120초, 설정 불가)

### 5.6 [MEDIUM] 순환 의존성 위험

`scheduler_alerts.py`에서 lazy import로 우회 중.

### 5.7 [LOW] Open Interest 현재값 USD 누락 → 0.0으로 저장

---

## 6. 아키텍처 설계 평가

### 잘된 점

1. **Async-first 설계:** 전체 I/O가 `asyncio` + `aiohttp` 기반으로 일관됨
2. **관심사 분리:** collectors / analyzers / storage / notifications 명확히 분리
3. **LLM 3단계 폴백:** JSON → 마크다운 추출 → 키워드 기반
4. **Graceful Shutdown:** SIGTERM/SIGINT 핸들러로 안전 종료
5. **Health Tracking:** 작업별 성공/실패 카운터 기록
6. **Data Integrity Reporter:** gap/duplicate 자동 검사

### 설계 우려사항

1. **단일 SQLite 파일** — 동시 쓰기 제한, 확장성 한계
2. **Out-of-scope 설정 클래스** — WebSocket, WhaleAlert 등 미사용 코드 포함

---

## 7. 우선순위별 개선 권고

### P0 (즉시 — 에이전트 동작을 위한 필수 수정)

1. **ATR 컬럼명 수정** — `volatility.py`에서 `ATR_{period}` → pandas-ta 원래 이름 사용, 또는 builder에서 `ATR_14`로 조회
2. **BB 컬럼명 수정** — `volatility.py`에서 실제 pandas-ta 컬럼명 사용, 또는 builder에서 `BBU_20_2.0_2.0` 등으로 조회
3. **SMA_200 lookback 확대** — `lookback_candles` 200 이상으로 변경, 또는 불충분 시 프롬프트에 명시
4. **프롬프트 개선** — 분석 프레임워크, 각 필드 설명, confidence 기준 등을 프롬프트에 포함
5. **Support/Resistance를 Context에 추가** — 이미 구현된 분석기 연결
6. **Volume 분석기(OBV, VWAP) Context에 추가** — 이미 구현된 분석기 연결

### P1 (1주 내)
7. **Fear & Greed 수집기에 retry 로직 추가**
8. **DB 트랜잭션 batch 처리**
9. **`datetime.utcnow()` 전환**
10. **미평가 예측 TTL 구현**

### P2 (2주 내)
11. **Claude Agent 타임아웃 설정 외부화**
12. **디스코드 전송 이력 로깅**
13. **미사용 설정 클래스 제거**

---

## 8. 결론

**에이전트가 정상 동작하지 않는 핵심 원인:** 기술적 지표 컬럼명 불일치로 인해 에이전트에 전달되는 ATR, Bollinger Bands, SMA 200 데이터가 모두 가짜 fallback 값임. 에이전트는 "ATR $0.00 (변동성 없음)", "BB 밴드폭 ±2%", "SMA 200 = 현재가"라는 비현실적 데이터로 분석을 수행하고 있어, 의미 있는 예측이 불가능한 상태.

추가로, 이미 구현된 Support/Resistance와 Volume 분석기가 에이전트에 연결되지 않아 핵심 분석 데이터가 누락됨. 프롬프트에도 구조화된 분석 가이드가 없어 에이전트의 출력 품질이 불안정함.

**전체 등급: D+** — 파이프라인 골격은 완성되었으나, 데이터 파이프라인의 중간 단계에서 critical한 데이터 왜곡이 발생하여 에이전트 분석이 의미 없는 상태.

**수정 범위:** P0 항목(컬럼명 수정, lookback 확대, 프롬프트 개선, 분석기 연결)만 해결하면 에이전트가 정상적인 데이터로 분석을 수행할 수 있게 됨. 코드 변경량은 적지만 영향도가 매우 큼.
