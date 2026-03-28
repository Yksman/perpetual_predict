# Prediction Debiasing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시드데이터에서 방향 프라이밍을 제거하고, 에이전트 프롬프트에 추세/역추세 양방향 관점을 추가하여 예측 편향을 완화한다.

**Architecture:** 3개 분석기 출력(market_structure, divergence, ema_distance)의 프롬프트 표현을 수정하고, predictor.md에 Perspective 섹션을 추가한다. 기존 데이터클래스/분석 로직은 변경하지 않으며, 프롬프트에 노출되는 텍스트만 수정한다.

**Tech Stack:** Python 3.13, pandas, pytest, ruff

---

### Task 1: market_structure — "Current Structure" 라벨 제거

**Files:**
- Modify: `perpetual_predict/analyzers/technical/market_structure.py:186-204`
- Test: `tests/test_analyzers/test_market_structure.py`

- [ ] **Step 1: 테스트 추가 — summary에 방향 라벨이 없는지 검증**

`tests/test_analyzers/test_market_structure.py` 끝에 추가:

```python
class TestMarketStructureSummaryDebiasing:
    def test_summary_has_no_directional_labels(self):
        """Summary should not contain Bullish/Bearish/Transition labels."""
        prices = []
        for i in range(30):
            base = 100 + i * 0.5 + (3 if i % 6 < 3 else -1)
            prices.append((base, base + 2, base - 1, base + 1))

        df = _make_ohlcv(prices)
        result = analyze_market_structure(df, left_bars=2, right_bars=2)

        assert "Bullish" not in result.summary
        assert "Bearish" not in result.summary
        assert "Transition" not in result.summary
        # Structure Breaks count should still be present
        assert "Structure Breaks" in result.summary

    def test_summary_preserves_swing_data(self):
        """Summary should still contain swing point data and break markers."""
        prices = [
            (120, 122, 118, 121),
            (121, 125, 120, 124),
            (124, 128, 123, 127),
            (127, 127, 122, 123),
            (123, 124, 118, 119),
            (119, 120, 115, 116),
            (116, 118, 115, 117),
            (117, 120, 116, 119),
            (119, 123, 118, 122),
            (122, 122, 117, 118),
            (118, 119, 113, 114),
            (114, 115, 110, 111),
            (111, 113, 110, 112),
            (112, 114, 111, 113),
        ]
        df = _make_ohlcv(prices)
        result = analyze_market_structure(df, left_bars=2, right_bars=2)

        # Swing labels should be present
        assert any(label in result.summary for label in ("HH", "HL", "LH", "LL", "H", "L"))
        assert "$" in result.summary
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_analyzers/test_market_structure.py::TestMarketStructureSummaryDebiasing -v`
Expected: FAIL — summary에 "Bullish" 또는 "Bearish" 등이 포함되어 있어서 실패

- [ ] **Step 3: 구현 — `_build_summary()`에서 Current Structure 라인 제거**

`perpetual_predict/analyzers/technical/market_structure.py`의 `_build_summary()` 함수에서 `Current Structure` 라인을 제거:

```python
def _build_summary(
    swings: list[SwingPoint],
    structure: str,
    breaks: int,
) -> str:
    """Build human-readable market structure summary."""
    lines = []

    # Show recent swing sequence
    for i, swing in enumerate(swings, 1):
        marker = " ← Break" if _is_break_point(swings, i - 1) else ""
        lines.append(
            f"  {i}. ${swing.price:,.0f} ({swing.label}){marker}"
        )

    lines.append(f"  Structure Breaks: {breaks}")

    return "\n".join(lines)
```

변경: `lines.append(f"  Current Structure: {structure}")` 라인 삭제. `current_structure` 필드는 `MarketStructureResult` 데이터클래스에 그대로 유지 (내부 로직용).

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_analyzers/test_market_structure.py -v`
Expected: ALL PASS

- [ ] **Step 5: 커밋**

```bash
git add perpetual_predict/analyzers/technical/market_structure.py tests/test_analyzers/test_market_structure.py
git commit -m "refactor: remove directional labels from market_structure summary"
```

---

### Task 2: divergences — Bullish/Bearish 라벨 제거

**Files:**
- Modify: `perpetual_predict/analyzers/technical/divergence.py:270-293`
- Test: `tests/test_analyzers/test_divergence.py`

- [ ] **Step 1: 테스트 추가 — summary에 방향 라벨이 없는지 검증**

`tests/test_analyzers/test_divergence.py` 끝에 추가:

```python
from perpetual_predict.analyzers.technical.divergence import (
    Divergence,
    _build_divergence_summary,
)


class TestDivergenceSummaryDebiasing:
    def test_summary_has_no_directional_labels(self):
        """Summary should not contain Bullish/Bearish direction labels."""
        divs = [
            Divergence(
                type="bearish",
                indicator="MACD",
                price_point_1=70000,
                price_point_2=72000,
                indicator_point_1=357,
                indicator_point_2=223,
                index_1=10,
                index_2=20,
                strength="regular",
            ),
            Divergence(
                type="bullish",
                indicator="RSI",
                price_point_1=69000,
                price_point_2=67000,
                indicator_point_1=30,
                indicator_point_2=35,
                index_1=15,
                index_2=25,
                strength="regular",
            ),
        ]
        summary = _build_divergence_summary(divs)

        assert "Bearish" not in summary
        assert "Bullish" not in summary
        # Raw patterns should still be present
        assert "HH" in summary
        assert "LL" in summary
        assert "MACD" in summary
        assert "RSI" in summary
        assert "Regular" in summary

    def test_hidden_divergence_no_labels(self):
        """Hidden divergences should also not have direction labels."""
        divs = [
            Divergence(
                type="bearish",
                indicator="MACD",
                price_point_1=72000,
                price_point_2=71000,
                indicator_point_1=200,
                indicator_point_2=250,
                index_1=10,
                index_2=20,
                strength="hidden",
            ),
        ]
        summary = _build_divergence_summary(divs)

        assert "Bearish" not in summary
        assert "Hidden" in summary
        assert "LH" in summary
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_analyzers/test_divergence.py::TestDivergenceSummaryDebiasing -v`
Expected: FAIL — summary에 "Bearish", "Bullish" 포함

- [ ] **Step 3: 구현 — `_build_divergence_summary()`에서 방향 라벨 제거**

`perpetual_predict/analyzers/technical/divergence.py`의 `_build_divergence_summary()` 수정:

```python
def _build_divergence_summary(divergences: list[Divergence]) -> str:
    """Build human-readable divergence summary for LLM prompt."""
    if not divergences:
        return "  No divergences detected in recent candles"

    lines = []
    for d in divergences:
        strength_label = "Regular" if d.strength == "regular" else "Hidden"

        if d.type == "bullish":
            price_pattern = "LL" if d.strength == "regular" else "HL"
            ind_pattern = "HL" if d.strength == "regular" else "LL"
        else:
            price_pattern = "HH" if d.strength == "regular" else "LH"
            ind_pattern = "LH" if d.strength == "regular" else "HH"

        lines.append(
            f"  - {d.indicator} {strength_label}: "
            f"Price {price_pattern} (${d.price_point_1:,.0f}→${d.price_point_2:,.0f}), "
            f"{d.indicator} {ind_pattern} ({d.indicator_point_1:.1f}→{d.indicator_point_2:.1f})"
        )

    return "\n".join(lines)
```

변경: `f"{d.indicator} {strength_label} {direction}: "` → `f"{d.indicator} {strength_label}: "` — `direction` 변수와 관련 코드 제거.

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_analyzers/test_divergence.py -v`
Expected: ALL PASS

- [ ] **Step 5: 커밋**

```bash
git add perpetual_predict/analyzers/technical/divergence.py tests/test_analyzers/test_divergence.py
git commit -m "refactor: remove directional labels from divergence summary"
```

---

### Task 3: ema_distance 모듈 → trend 통합

**Files:**
- Modify: `perpetual_predict/llm/context/builder.py:145-190, 219-226, 228-240`
- Modify: `perpetual_predict/experiment/models.py:11-27`
- Test: `tests/test_llm/test_context_debiasing.py`

- [ ] **Step 1: 테스트 추가 — trend 섹션에 EMA 거리가 포함되고, ema_distance가 별도 섹션으로 없는지 검증**

`tests/test_llm/test_context_debiasing.py` 끝에 추가:

```python
class TestEmaDistanceIntegration:
    """Verify EMA distances are integrated into trend section, not separate."""

    def test_trend_section_includes_ema_distances(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=0.0,
            price_change_24h=0.0,
            high_24h=70000.0,
            low_24h=70000.0,
            volume_24h=0.0,
            sma_20=69000.0,
            sma_50=68000.0,
            sma_200=65000.0,
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
            dist_ema_9=0.45,
            dist_ema_21=-1.22,
            dist_ema_55=-4.82,
            dist_ema_200=-0.12,
        )
        section = ctx._section_trend()

        assert "EMA 9" in section
        assert "EMA 21" in section
        assert "EMA 55" in section
        assert "EMA 200" in section
        assert "+0.45%" in section
        assert "-1.22%" in section

    def test_format_prompt_no_ema_distance_section(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=0.0,
            price_change_24h=0.0,
            high_24h=70000.0,
            low_24h=70000.0,
            volume_24h=0.0,
            sma_20=69000.0,
            sma_50=68000.0,
            sma_200=65000.0,
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
        )
        prompt = ctx.format_prompt()

        assert "### EMA Distance" not in prompt
        assert "### Trend Indicators" in prompt
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_llm/test_context_debiasing.py::TestEmaDistanceIntegration -v`
Expected: FAIL — trend 섹션에 EMA 거리가 없고, EMA Distance 섹션이 별도로 존재

- [ ] **Step 3: 구현 — `_section_trend()`에 EMA 거리 통합**

`perpetual_predict/llm/context/builder.py`의 `_section_trend()` 수정:

```python
    def _section_trend(self) -> str:
        sma_20_dist = ((self.current_price - self.sma_20) / self.sma_20) * 100
        sma_50_dist = ((self.current_price - self.sma_50) / self.sma_50) * 100
        sma_200_dist = ((self.current_price - self.sma_200) / self.sma_200) * 100
        return (
            f"### Trend Indicators\n"
            f"- SMA 20: ${self.sma_20:,.2f} ({sma_20_dist:+.2f}%)\n"
            f"- SMA 50: ${self.sma_50:,.2f} ({sma_50_dist:+.2f}%)\n"
            f"- SMA 200: ${self.sma_200:,.2f} ({sma_200_dist:+.2f}%)\n"
            f"- EMA 9: {self.dist_ema_9:+.2f}% | EMA 21: {self.dist_ema_21:+.2f}% | "
            f"EMA 55: {self.dist_ema_55:+.2f}% | EMA 200: {self.dist_ema_200:+.2f}%\n"
            f"- MACD: {self.macd:.2f} | Signal: {self.macd_signal:.2f} | Histogram: {self.macd_histogram:.2f}\n"
            f"- ADX: {self.adx:.1f}"
        )
```

변경: EMA 12/26 절대값 라인을 EMA 거리% 라인으로 교체.

- [ ] **Step 4: 구현 — `format_prompt()`에서 ema_distance 제거**

`perpetual_predict/llm/context/builder.py`의 `format_prompt()` 수정 — `ema_distance` 블록 제거:

```python
    def format_prompt(self, enabled_modules: list[str] | None = None) -> str:
        from perpetual_predict.experiment.models import DEFAULT_MODULES

        modules = set(enabled_modules or DEFAULT_MODULES)
        sections = [self._section_header()]

        if "price_action" in modules:
            sections.append(self._section_price_action())
        if "candle_structure" in modules:
            sections.append(self._section_candle_structure())
        if "trend" in modules:
            sections.append(self._section_trend())
        if "momentum" in modules:
            sections.append(self._section_momentum())
        if "volatility" in modules:
            sections.append(self._section_volatility())
        if "cvd" in modules:
            sections.append(self._section_cvd())
        if "liquidation" in modules:
            sections.append(self._section_liquidation())
        if "sentiment" in modules:
            sections.append(self._section_sentiment())
        if "market_structure" in modules:
            sections.append(self._section_market_structure())
        if "divergences" in modules:
            sections.append(self._section_divergences())
        if "support_resistance" in modules:
            sections.append(self._section_support_resistance())
        if "macro" in modules:
            sections.append(self._section_macro())
        if "recent_candles" in modules:
            sections.append(self._section_recent_candles())

        sections.append(self._section_footer(
            include_portfolio="portfolio" in modules,
        ))

        return "\n\n".join(s for s in sections if s)
```

변경: `if "ema_distance" in modules:` 블록 제거. `_section_ema_distance()` 메서드는 그대로 유지 (하위 호환, 직접 호출 가능).

- [ ] **Step 5: 구현 — SEED_MODULES에서 ema_distance 제거**

`perpetual_predict/experiment/models.py`:

```python
SEED_MODULES = [
    "price_action",
    "candle_structure",
    "trend",
    "momentum",
    "volatility",
    "cvd",
    "liquidation",
    "sentiment",
    "market_structure",
    "divergences",
    "support_resistance",
    "recent_candles",
    "portfolio",
    "macro",
]
```

변경: `"ema_distance"` 항목 제거.

- [ ] **Step 6: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_llm/test_context_debiasing.py -v`
Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add perpetual_predict/llm/context/builder.py perpetual_predict/experiment/models.py tests/test_llm/test_context_debiasing.py
git commit -m "refactor: integrate ema_distance into trend section, remove duplicate module"
```

---

### Task 4: predictor.md — Perspective 섹션 추가

**Files:**
- Modify: `.claude/agents/predictor.md`

- [ ] **Step 1: Perspective 섹션 추가**

`.claude/agents/predictor.md`의 `## Decision Process` 섹션과 `## Output` 섹션 사이에 추가:

```markdown
## Perspective

Every 4H candle exists in tension between two forces:
- **Trend continuation**: the dominant direction has momentum and structural backing
- **Mean reversion**: extreme readings attract counter-moves, and trends exhaust

Both deserve equal analytical weight. A strong trend makes the reversal case harder — but when the reversal case does overcome that bar, the move is often sharp. Dismissing either side with surface-level reasoning is a blind spot.
```

- [ ] **Step 2: 커밋**

```bash
git add .claude/agents/predictor.md
git commit -m "refactor: add balanced perspective framing to predictor agent"
```

---

### Task 5: 전체 검증

**Files:**
- All modified files

- [ ] **Step 1: 린트 실행**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 2: 전체 테스트 실행**

Run: `pytest -v`
Expected: ALL PASS

- [ ] **Step 3: 프롬프트 출력 검증 — 방향 라벨 완전 제거 확인**

Run: `python -c "from perpetual_predict.llm.context.builder import MarketContext; ctx = MarketContext(current_price=70000, price_change_4h=-1.0, price_change_24h=-3.0, high_24h=72000, low_24h=68000, volume_24h=50000, sma_20=71000, sma_50=72000, sma_200=69000, ema_12=70500, ema_26=71000, macd=-500, macd_signal=-300, macd_histogram=-200, bb_upper=73000, bb_middle=71000, bb_lower=69000, market_structure_summary='  1. \$72000 (HH)\n  2. \$70000 (HL)\n  3. \$71000 (LH)\n  Structure Breaks: 1', divergence_summary='  - MACD Regular: Price HH, MACD LH'); prompt = ctx.format_prompt(); assert 'EMA Distance' not in prompt; assert 'Bullish' not in prompt.split('Divergences')[1] if 'Divergences' in prompt else True; print('PASS: No directional labels in prompt')"`

Expected: `PASS: No directional labels in prompt`

- [ ] **Step 4: 최종 커밋 (필요 시 린트 수정)**

린트나 테스트에서 발견된 이슈가 있으면 수정 후:
```bash
git add -A
git commit -m "fix: address lint/test issues from debiasing changes"
```
