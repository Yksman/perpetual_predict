# Prediction Debiasing: 추세/역추세 균형 개선

## Problem

28건 baseline 예측 분석 결과, 에이전트가 DOWN을 89% (25/28) 예측하며 50% 적중률을 보임. 시장 실제 DOWN 비율은 50%. 원인:

1. **서술형 라벨 프라이밍**: `market_structure`의 "Current Structure: Bearish", `divergences`의 "Bearish Divergence" 라벨이 판단을 고착
2. **중복 정보 편향 강화**: `ema_distance`와 `trend` 모듈이 동일한 "가격 vs 이동평균" 정보를 2번 제공 → 같은 약세 신호를 이중 앵커링
3. **역추세 관점 부재**: `predictor.md`에 추세 지속과 평균회귀 양방향을 동등하게 분석하라는 프레이밍 없음

## Solution

### 1. market_structure — 방향 라벨 제거

`_build_summary()`에서 `Current Structure: {Bearish|Bullish|Transition}` 라인 제거. HH/HL/LH/LL 시퀀스와 Structure Breaks 카운트는 원시 데이터이므로 유지.

**Before:**
```
  1. $72,000 (HH)
  2. $70,500 (HL)
  3. $71,800 (LH) ← Break
  4. $69,200 (LL) ← Break
  Current Structure: Bearish
  Structure Breaks: 2
```

**After:**
```
  1. $72,000 (HH)
  2. $70,500 (HL)
  3. $71,800 (LH) ← Break
  4. $69,200 (LL) ← Break
  Structure Breaks: 2
```

Files: `analyzers/technical/market_structure.py`

### 2. divergences — 방향 라벨 제거

`_build_divergence_summary()`에서 `Bullish`/`Bearish` 텍스트 제거. "Price HH + MACD LH" 같은 원시 패턴 관계는 유지.

**Before:**
```
  - MACD Regular Bearish: Price HH ($72,000→$71,800), MACD LH (357.0→223.0)
```

**After:**
```
  - MACD Regular: Price HH ($72,000→$71,800), MACD LH (357.0→223.0)
```

Files: `analyzers/technical/divergence.py`

### 3. ema_distance 모듈 → trend 통합

`ema_distance` 모듈의 EMA 9/21/55/200 거리 정보를 `trend` 섹션에 한 줄로 통합. 별도 모듈 제거.

**After (trend section):**
```
### Trend Indicators
- SMA 20: $70,253 (-1.91%)
- SMA 50: $71,500 (-3.50%)
- SMA 200: $69,232 (-0.08%)
- EMA 9: -0.45% | EMA 21: -1.22% | EMA 55: -4.82% | EMA 200: -0.12%
- MACD: -723.11 | Signal: -331.23 | Histogram: -391.88
- ADX: 23.1
```

Files: `llm/context/builder.py`, `experiment/models.py`

### 4. predictor.md — 양방향 관점 프레이밍

Decision Process 뒤에 Perspective 섹션 추가:

```markdown
## Perspective

Every 4H candle exists in tension between two forces:
- **Trend continuation**: the dominant direction has momentum and structural backing
- **Mean reversion**: extreme readings attract counter-moves, and trends exhaust

Both deserve equal analytical weight. A strong trend makes the reversal case harder —
but when the reversal case does overcome that bar, the move is often sharp.
Dismissing either side with surface-level reasoning is a blind spot.
```

Files: `.claude/agents/predictor.md`

## Scope

- baseline과 variant 모두 동일 반영
- A/B 테스트 미설계 (전체 적용)
- 모듈 시스템 아키텍처, 에이전트 출력 스키마, 다른 모듈 변경 없음

## Files Changed

| File | Change |
|------|--------|
| `analyzers/technical/market_structure.py` | `_build_summary()` — "Current Structure" 라인 제거 |
| `analyzers/technical/divergence.py` | `_build_divergence_summary()` — Bullish/Bearish 라벨 제거 |
| `llm/context/builder.py` | `_section_trend()` — EMA 거리 통합, `format_prompt()` — ema_distance 제거 |
| `experiment/models.py` | `SEED_MODULES` — `ema_distance` 제거 |
| `.claude/agents/predictor.md` | Perspective 섹션 추가 |
| Tests | 관련 테스트 업데이트 |
