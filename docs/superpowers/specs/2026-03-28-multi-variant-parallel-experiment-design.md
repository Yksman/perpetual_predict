# Multi-Variant Parallel Experiment Design

## Overview

기존 A/B 테스트 프레임워크를 확장하여 하나의 실험에 복수 variant arm을 정의하고, 예측 에이전트를 병렬로 동시 실행하는 구조.

**목표**: `experiment create --variant macro --variant news --variant macro,news` 로 한 실험 안에 여러 모듈 조합을 동시에 테스트. 최대 4개 predictor를 병렬 실행하여 동일 시장 조건에서 공정하게 비교.

## Experiment Model Change

### 현재 → 변경

```python
# 현재
@dataclass
class Experiment:
    control_modules: list[str]
    variant_modules: list[str]  # 단일 variant

# 변경
@dataclass
class Experiment:
    control_modules: list[str]
    variants: dict[str, list[str]]  # {variant_name: enabled_modules}
```

### DB 저장

DB 스키마 변경 없음. `variant_modules` 컬럼에 dict JSON을 저장:

```python
# 단일 variant (기존)
{"variant": ["price_action", "trend", ..., "macro"]}

# 멀티 variant (변경)
{
    "macro": ["price_action", "trend", ..., "macro"],
    "news": ["price_action", "trend", ..., "news"],
    "macro_news": ["price_action", "trend", ..., "macro", "news"]
}
```

### 마이그레이션

기존 실험 데이터(단일 variant)를 새 형식으로 변환:

```python
# 기존: variant_modules = ["price_action", ..., "macro"]
# 변환: variant_modules = {"variant": ["price_action", ..., "macro"]}
```

`Experiment.from_dict()`에서 list 타입이면 자동으로 `{"variant": list}` 형태로 변환하여 하위 호환성 유지.

### Paper Trading 계정

각 variant별 독립 계정:

```
"{experiment_id}_control"             → baseline 공유 (기존과 동일)
"{experiment_id}_variant_macro"       → variant "macro" 전용
"{experiment_id}_variant_news"        → variant "news" 전용
"{experiment_id}_variant_macro_news"  → variant "macro_news" 전용
```

## CLI Interface

### 실험 생성

```bash
# 멀티 variant
experiment create --name test_modules --variant macro --variant news --variant macro,news

# 단일 variant (기존 호환)
experiment create --name test_macro --variant macro
```

각 `--variant` 값이 하나의 arm. 쉼표로 모듈 조합 표현. `--add` 플래그는 deprecated → `--variant`로 통일.

### 실험 상태

```bash
$ experiment status <id>

Experiment: test_modules (active, 45 samples)

  control (baseline):     accuracy 52.2%, net_return -1.3%, sharpe 0.12
  variant_macro:          accuracy 55.6%, net_return +2.1%, sharpe 0.45  (p=0.12)
  variant_news:           accuracy 58.9%, net_return +4.2%, sharpe 0.67  (p=0.04) ✓
  variant_macro_news:     accuracy 56.7%, net_return +3.1%, sharpe 0.51  (p=0.08)
```

`✓` = p-value < significance level

### 실험 병합

```bash
# 최고 성과 variant 자동 선택
experiment merge <id>

# 특정 variant 지정
experiment merge <id> --variant news
```

## Parallel Prediction Execution

### 실행 흐름

```
4H Cycle - Predict Phase
│
├─ Market Context 빌드 (1회, 공유)
│
├─ asyncio.gather() 병렬 실행 (최대 4개):
│   ├─ baseline: format_prompt(DEFAULT_MODULES) → claude -p → "default" account
│   ├─ variant_macro: format_prompt([...,"macro"]) → claude -p → "{exp}_variant_macro" account
│   ├─ variant_news: format_prompt([...,"news"]) → claude -p → "{exp}_variant_news" account
│   └─ variant_macro_news: format_prompt([...,"macro","news"]) → claude -p → "{exp}_variant_macro_news" account
│
└─ 각 결과 → DB 저장 + Paper Trade
```

### 병렬 실행 규칙

- Market Context는 1회만 빌드, 모든 arm에 공유 (공정한 비교 보장)
- 각 arm은 `format_prompt(enabled_modules)`만 다르게 호출
- `claude -p`는 독립 subprocess → 완전한 프로세스 격리 확인됨
- 최대 동시 실행 수: 4개 (baseline 포함). 초과 시 나머지는 순차 실행
- 10초 cooldown 제거 — 독립 프로세스이므로 불필요

### 동시 실행 제한 구현

```python
# baseline + active variants
prediction_tasks = [baseline_task] + variant_tasks

# max 4개씩 배치 실행
MAX_CONCURRENT = 4
for batch_start in range(0, len(prediction_tasks), MAX_CONCURRENT):
    batch = prediction_tasks[batch_start:batch_start + MAX_CONCURRENT]
    batch_results = await asyncio.gather(*batch, return_exceptions=True)
```

## Statistical Analysis

### 분석 방식

각 variant를 control과 독립적으로 1:1 비교 (기존 analyzer 로직 재사용):

```
control vs variant_macro      → p-value, accuracy diff, net_return diff
control vs variant_news       → p-value, accuracy diff, net_return diff
control vs variant_macro_news → p-value, accuracy diff, net_return diff
```

### Merge 로직

- 유의미한 variant (p < significance_level) 중 primary_metric 기준 최고 성과를 추천
- 해당 variant의 모듈들을 EXPERIMENTAL_MODULES에서 제거 → DEFAULT_MODULES에 자동 포함
- 사용자가 `--variant` 플래그로 특정 variant를 지정 가능

### 실험 완료 조건

모든 variant의 sample count가 min_samples 이상이어야 분석 가능.

## File Changes Summary

| File | Change |
|------|--------|
| `experiment/models.py` | Experiment 모델: `variant_modules` → `variants` dict, from_dict 하위 호환 |
| `experiment/analyzer.py` | 멀티 variant 루프 분석, variant별 1:1 비교 |
| `scheduler/jobs.py` | 병렬 예측 실행 (asyncio.gather), 10s cooldown 제거, max 4 concurrent |
| `cli/experiment.py` | `--variant` 플래그, status 멀티 variant 출력, merge --variant 옵션 |
| `storage/database.py` | Prediction 쿼리에서 variant name 지원 (arm 필드 활용) |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| 실험 구조 | 1개 실험 = N개 variant | 동일 시점/조건에서 공정 비교, 단일 실험 ID로 관리 |
| DB 스키마 | 변경 없음 (JSON 형식만 변경) | 마이그레이션 최소화, 하위 호환성 |
| 병렬 실행 | asyncio.gather + max 4 | 프로세스 격리 확인됨, 리소스 안정적 |
| cooldown | 제거 | 독립 subprocess이므로 불필요 |
| 통계 분석 | 1:1 비교 유지 | 기존 analyzer 재사용, 복잡도 최소화 |
| CLI | --variant 플래그 | 직관적, 조합 표현 (쉼표 구분) |
| 하위 호환 | from_dict에서 list→dict 자동 변환 | 기존 실험 데이터 깨지지 않음 |
