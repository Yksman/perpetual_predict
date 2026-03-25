# Reasoning Strategy Experiment Design

> 2026-03-24 Discord 논의 기반 정리

## Background

현재 시스템은 14개 시드 모듈로 4H BTCUSDT 방향을 예측한다.
`claude -p`에 시장 데이터를 텍스트로 넘기고, JSON으로 direction/confidence를 받는 구조.

### 현재 프롬프트 구조

프롬프트는 두 레이어로 구성:

1. **시스템 지시**: `.claude/agents/predictor.md` — 추론 철학과 출력 형식 정의
2. **유저 프롬프트**: `builder.py`가 생성하는 시장 데이터 + footer 지시문

```
predictor.md (시스템) + [시드데이터 + footer] (유저)
→ claude -p --json-schema
→ JSON 예측
```

### predictor.md 현재 내용

```markdown
# BTCUSDT 4H Futures Prediction Agent

## Philosophy
- Holistic interpretation: 개별 시그널이 아닌 전체를 읽어라
- Crowd dynamics: 다수의 포지셔닝과 그 반대를 고려하라
- Fluid judgment: 레짐이 변한다, 어제 작동한 것이 오늘 실패할 수 있다
```

추론 철학은 있지만 **구체적인 추론 스텝이 없다**. "전체를 읽어라"는 방향성이지 방법론이 아님.

### builder.py footer (유저 프롬프트 끝부분)

```
Based on this analysis, predict the direction of the CURRENT 4h candle (just started).
```

단순 지시. 추론 구조를 유도하지 않음.

## Core Insight: LLM-Native Edge

이 시스템이 전통 ML 모델 대비 가질 수 있는 고유 엣지:

1. **다중 지표의 맥락적 종합 판단** - XGBoost는 수치만 보지만, LLM은 지표 조합의 맥락을 해석할 수 있음
2. **사전 지식 기반 복합 패턴 인식** - 트레이딩 교과서에 있는 복합 패턴(BB 스퀴즈 + 거래량 감소 등)을 학습 데이터에서 이미 알고 있음
3. **레짐(regime) 인식** - 추세장/횡보장/변곡점을 판단하고 레짐에 맞는 전략 적용

현재 프롬프트 구조는 이 강점을 끌어내지 못하고 있다.

## Candidate Reasoning Structures

### Option 1: Adversarial Reasoning (Bull vs Bear)

```
Step 1: 주어진 데이터로 Bull case를 최대한 강하게 구성하라
Step 2: 주어진 데이터로 Bear case를 최대한 강하게 구성하라
Step 3: 두 주장의 강도를 비교하여 최종 판단하라
```

- **장점**: 확증 편향 방지, 양쪽 논거를 모두 검토하게 강제
- **위험**: 형식적으로 양쪽을 나열하고 결국 같은 결론일 수 있음
- **검증 방식**: LLM 추론 품질 개선에서 실제로 효과가 확인된 패턴 (Devil's Advocate)

### Option 2: Regime-First (레짐 선판단)

```
Step 1: 현재 시장 레짐을 판단하라 (Strong Trend / Weak Trend / Range / Transition)
Step 2: 판단한 레짐에서 가장 중요한 지표 3-5개를 선별하라
Step 3: 선별된 지표를 중심으로 예측하라
```

- **장점**: 횡보장에서 억지 예측 방지, 레짐별 다른 지표 가중
- **위험**: 레짐 판단 자체가 틀리면 이후 전부 틀림 (error propagation)

### Option 3: Pre-mortem (실패 시나리오 우선)

```
Step 1: 직관적 첫인상으로 방향을 판단하라
Step 2: 이 예측이 틀린다면 가장 가능성 높은 이유 3가지를 나열하라
Step 3: 각 실패 시나리오의 현실 가능성을 평가하라
Step 4: 리스크를 반영하여 최종 방향과 신뢰도를 결정하라
```

- **장점**: 과신 방지, confidence calibration에 도움
- **위험**: 지나치게 보수적이 될 수 있음 (NEUTRAL 편향)

## Implementation Approach

### 변경 대상

추론 전략 변경은 두 곳에 걸쳐 있다:

1. **`.claude/agents/predictor.md`** — 추론 철학/구조 (시스템 프롬프트)
2. **`builder.py`의 `_section_footer()`** — 구체적 지시문 (유저 프롬프트)

predictor.md가 "어떻게 사고하라"를 정의하고, footer가 "무엇을 출력하라"를 정의.
추론 구조 변경은 주로 **predictor.md**에서 이루어져야 한다.

JSON schema(출력 형식)는 동일하게 유지 가능.

```
# 실험 시 구조
predictor.md → predictor_adversarial.md (variant용 별도 에이전트 파일)
또는
predictor.md 내에 reasoning_strategy에 따라 분기
```

### A/B 테스트 통합

현재 실험 프레임워크는 `enabled_modules`만 변수로 지원.
추론 전략을 테스트하려면:

1. `Experiment` 모델에 `reasoning_strategy` 필드 추가
2. `_run_single_prediction`에 reasoning_strategy 파라미터 전달
3. `format_prompt()`가 reasoning_strategy에 따라 다른 footer 생성

### 2x2 Factorial Design (향후)

```
              현재 추론        Adversarial 추론
매크로 X  |  Arm A (control) |  Arm B           |
매크로 O  |  Arm C           |  Arm D           |
```

- 4-arm 설계: 매 사이클 `claude -p` 4번 호출
- 비용: 하루 6사이클 × 4arm = 24회/일
- 최소 샘플: arm당 30개 × 4 = 5일 (120개 총 예측)
- 상호작용 효과 검출에는 더 많은 샘플 필요

### 권장 실행 순서

1. **매크로 A/B 테스트 완료** (현재 진행중)
2. **추론 전략 A/B 테스트** (매크로 결과 반영 후)
3. 두 실험 결과 기반으로 2x2 필요 여부 판단

순차 실험이 현실적인 이유:
- 현재 2-arm 구조 그대로 사용 가능
- 호출 비용 동일
- 샘플 부족으로 상호작용 효과 검출이 어려움

## Evaluation Criteria

추론 전략 변경의 효과를 판단하는 기준:

1. **방향 정확도**: 예측 방향 일치율 (primary)
2. **net_return**: 수수료 차감 후 수익률
3. **confidence calibration**: 높은 신뢰도 예측이 실제로 더 정확한가
4. **NEUTRAL 비율**: 지나치게 보수적이지 않은가

## Rejected Approaches (논의 중 기각된 아이디어)

### 시드데이터 추가

- 기술적 지표 추가 (오더북, VWAP, 테이커 비율, 1D 타임프레임)
- 기각 이유: 기존 14개 모듈이 이미 4H TA를 충분히 커버. 추가 데이터가 예측 방향을 바꿀 만큼의 임팩트가 없을 가능성 높음.

### 프롬프트 엔지니어링 (문구 개선)

- 기각 이유: 같은 데이터가 들어가면 지시문 문구를 다듬어도 LLM 판단이 크게 달라지지 않음. 추론 "구조" 변경과는 다른 문제.

### RAG 기반 예측-평가 지식 축적

- 기각 이유: 시장 데이터 유사도를 텍스트 임베딩으로 정의하기 어렵고, 샘플 부족으로 조건부 패턴에 통계적 의미 없음. 구조화된 수치 패턴이면 ML 모델이 더 적합.
