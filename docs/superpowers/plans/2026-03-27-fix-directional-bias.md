# Fix Directional Bias — Bull/Bear Case Framework

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the agent's directional anchoring bias by forcing bilateral (bull/bear) analysis before direction selection, and removing pre-interpreted labels from the context data.

**Architecture:** Three-layer fix: (1) restructure agent prompt to require explicit bull_case and bear_case probability assessment before final direction call, (2) add bull/bear fields to JSON schema and AgentResult with system-level consistency validation, (3) remove directional labels ("Bullish/Bearish/above/below") from context builder so the agent works from raw numbers only.

**Tech Stack:** Python 3.12, SQLite (aiosqlite), Claude Code CLI (`claude -p --agent`)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `.claude/agents/predictor.md` | Modify | Agent prompt: add bull/bear case framework |
| `perpetual_predict/llm/agent/runner.py` | Modify | JSON schema + AgentResult + post-processing validation |
| `perpetual_predict/llm/context/builder.py` | Modify | Remove directional labels from `_section_trend()` and `_summarize_recent_candles()` |
| `perpetual_predict/storage/models.py` | Modify | Add `bull_case`/`bear_case` fields to Prediction dataclass |
| `perpetual_predict/storage/database.py` | Modify | Add migration + insert/select for new columns |
| `perpetual_predict/scheduler/jobs.py` | Modify | Map new AgentResult fields to Prediction |
| `perpetual_predict/notifications/scheduler_alerts.py` | Modify | Display bull/bear probabilities in Discord embed |
| `tests/test_llm/test_runner_validation.py` | Create | Tests for bull/bear validation logic |
| `tests/test_llm/test_context_debiasing.py` | Create | Tests for label removal in context builder |

---

### Task 1: Remove directional labels from context builder

**Files:**
- Modify: `perpetual_predict/llm/context/builder.py:228-240` (`_section_trend`)
- Modify: `perpetual_predict/llm/context/builder.py:635-668` (`_summarize_recent_candles`)
- Test: `tests/test_llm/test_context_debiasing.py`

- [ ] **Step 1: Write tests for debiased context output**

```python
# tests/test_llm/test_context_debiasing.py
"""Tests for directional label removal from context builder."""

from perpetual_predict.llm.context.builder import MarketContext


class TestTrendSectionDebiasing:
    """Verify _section_trend uses only numbers, no above/below labels."""

    def test_no_above_below_labels(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=1.0,
            price_change_24h=2.0,
            high_24h=71000.0,
            low_24h=69000.0,
            volume_24h=50000.0,
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
        section = ctx._section_trend()
        assert "above" not in section.lower()
        assert "below" not in section.lower()
        # Distance percentages should be present
        assert "%" in section
        # SMA values should still be present
        assert "69,000" in section  # SMA 20
        assert "68,000" in section  # SMA 50
        assert "65,000" in section  # SMA 200

    def test_shows_distance_percentages(self):
        ctx = MarketContext(
            current_price=70000.0,
            price_change_4h=0.0,
            price_change_24h=0.0,
            high_24h=70000.0,
            low_24h=70000.0,
            volume_24h=0.0,
            sma_20=69000.0,  # price is +1.45% from SMA 20
            sma_50=68000.0,  # price is +2.94% from SMA 50
            sma_200=65000.0,  # price is +7.69% from SMA 200
            ema_12=69500.0,
            ema_26=69000.0,
            macd=500.0,
            macd_signal=400.0,
            macd_histogram=100.0,
            bb_upper=72000.0,
            bb_middle=70000.0,
            bb_lower=68000.0,
        )
        section = ctx._section_trend()
        assert "+1.45%" in section
        assert "+2.94%" in section
        assert "+7.69%" in section


class TestRecentCandlesDebiasing:
    """Verify _summarize_recent_candles uses neutral pattern names."""

    def _make_context_with_candles(self, candle_data: list[dict]) -> MarketContext:
        """Helper to create a context and generate candle summary."""
        import pandas as pd

        from perpetual_predict.llm.context.builder import MarketContextBuilder

        df = pd.DataFrame(candle_data)
        # Use the builder's method directly
        builder = MarketContextBuilder.__new__(MarketContextBuilder)
        summary = builder._summarize_recent_candles(df)
        return summary

    def test_no_bullish_bearish_labels(self):
        candles = [
            {"open": 100, "high": 110, "low": 95, "close": 108, "volume": 1000},
            {"open": 108, "high": 112, "low": 100, "close": 102, "volume": 1200},
            {"open": 102, "high": 105, "low": 98, "close": 104, "volume": 900},
        ]
        summary = self._make_context_with_candles(candles)
        assert "bullish" not in summary.lower()
        assert "bearish" not in summary.lower()

    def test_no_shooting_star_hanging_man(self):
        # Candle with big upper wick (would have been "Shooting Star")
        candles = [
            {"open": 100, "high": 120, "low": 99, "close": 98, "volume": 1000},
            # Candle with big lower wick (would have been "Hanging Man")
            {"open": 100, "high": 101, "low": 80, "close": 98, "volume": 1000},
        ]
        summary = self._make_context_with_candles(candles)
        assert "shooting star" not in summary.lower()
        assert "hanging man" not in summary.lower()

    def test_uses_neutral_pattern_names(self):
        # Doji should remain (already neutral)
        candles = [
            {"open": 100, "high": 110, "low": 90, "close": 100.5, "volume": 1000},
        ]
        summary = self._make_context_with_candles(candles)
        assert "Doji" in summary

    def test_wick_descriptions_are_structural(self):
        # Big upper wick candle
        candles = [
            {"open": 100, "high": 120, "low": 99, "close": 98, "volume": 1000},
        ]
        summary = self._make_context_with_candles(candles)
        # Should describe the structure, not the implication
        assert "Upper Wick" in summary or "Long Upper" in summary

    def test_body_descriptions_are_structural(self):
        # Strong positive candle
        candles = [
            {"open": 100, "high": 112, "low": 99, "close": 110, "volume": 1000},
        ]
        summary = self._make_context_with_candles(candles)
        # Should have a sign-based description, not "Bullish"
        assert "+" in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm/test_context_debiasing.py -v`
Expected: FAIL — `_section_trend` still contains "above"/"below", `_summarize_recent_candles` still uses "Bullish"/"Bearish"/"Shooting Star"/"Hanging Man"

- [ ] **Step 3: Remove directional labels from `_section_trend()`**

Replace `_section_trend()` in `perpetual_predict/llm/context/builder.py:228-240` with:

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
            f"- EMA 12/26: ${self.ema_12:,.2f} / ${self.ema_26:,.2f}\n"
            f"- MACD: {self.macd:.2f} | Signal: {self.macd_signal:.2f} | Histogram: {self.macd_histogram:.2f}\n"
            f"- ADX: {self.adx:.1f}"
        )
```

- [ ] **Step 4: Replace directional labels in `_summarize_recent_candles()`**

Replace `_summarize_recent_candles()` in `perpetual_predict/llm/context/builder.py:635-668` with:

```python
    def _summarize_recent_candles(self, df: pd.DataFrame) -> str:
        """Generate human-readable summary of recent candles with neutral labels."""
        lines = []
        for i, (_, row) in enumerate(df.iterrows(), 1):
            change = self._pct_change(row["close"], row["open"])
            direction = "+" if change >= 0 else ""

            # Simple pattern detection using structural (non-directional) names
            body = abs(row["close"] - row["open"])
            upper_wick = row["high"] - max(row["close"], row["open"])
            lower_wick = min(row["close"], row["open"]) - row["low"]
            total_range = row["high"] - row["low"]

            if total_range > 0:
                body_pct = body / total_range * 100
                if body_pct < 20:
                    pattern = "Doji"
                elif upper_wick > body * 2:
                    pattern = "Long Upper Wick"
                elif lower_wick > body * 2:
                    pattern = "Long Lower Wick"
                else:
                    pattern = "Full Body"
            else:
                pattern = "Flat"

            lines.append(
                f"  {i}. {direction}{change:.2f}% | "
                f"O: ${row['open']:,.0f} H: ${row['high']:,.0f} "
                f"L: ${row['low']:,.0f} C: ${row['close']:,.0f} | {pattern}"
            )

        return "\n".join(lines)
```

- [ ] **Step 5: Create `tests/test_llm/__init__.py` and run tests**

```bash
touch tests/test_llm/__init__.py
```

Run: `pytest tests/test_llm/test_context_debiasing.py -v`
Expected: All PASS

- [ ] **Step 6: Verify existing macro tests still pass**

Run: `pytest tests/test_macro/test_context_macro.py -v`
Expected: All PASS (macro section was already debiased)

- [ ] **Step 7: Commit**

```bash
git add tests/test_llm/ perpetual_predict/llm/context/builder.py
git commit -m "refactor: remove directional labels from context builder

Replace 'above/below' in trend section with signed distance percentages.
Replace 'Bullish/Bearish/Shooting Star/Hanging Man' candle patterns with
structural names (Full Body/Long Upper Wick/Long Lower Wick/Doji).
This prevents LLM anchoring on pre-interpreted directional labels."
```

---

### Task 2: Add bull/bear case fields to JSON schema and AgentResult

**Files:**
- Modify: `perpetual_predict/llm/agent/runner.py:15-62` (schema), `:65-79` (AgentResult), `:174-206` (parsing)
- Test: `tests/test_llm/test_runner_validation.py`

- [ ] **Step 1: Write tests for schema construction and result parsing**

```python
# tests/test_llm/test_runner_validation.py
"""Tests for bull/bear case validation in prediction runner."""

import json

from perpetual_predict.llm.agent.runner import (
    AgentResult,
    _build_prediction_schema,
    _validate_bull_bear_consistency,
)


class TestPredictionSchema:
    """Verify JSON schema includes bull_case and bear_case."""

    def test_schema_has_bull_bear_cases(self):
        schema = json.loads(_build_prediction_schema(3.0))
        props = schema["properties"]
        assert "bull_case" in props
        assert "bear_case" in props

    def test_bull_bear_are_required(self):
        schema = json.loads(_build_prediction_schema(3.0))
        assert "bull_case" in schema["required"]
        assert "bear_case" in schema["required"]

    def test_bull_bear_structure(self):
        schema = json.loads(_build_prediction_schema(3.0))
        bull = schema["properties"]["bull_case"]
        assert bull["type"] == "object"
        assert "probability" in bull["properties"]
        assert "reasoning" in bull["properties"]
        assert bull["properties"]["probability"]["minimum"] == 0.0
        assert bull["properties"]["probability"]["maximum"] == 1.0


class TestBullBearValidation:
    """Test _validate_bull_bear_consistency post-processing logic."""

    def test_high_bull_prob_overrides_down_direction(self):
        prediction = {
            "direction": "DOWN",
            "confidence": 0.4,
            "bull_case": {"probability": 0.65, "reasoning": "strong momentum"},
            "bear_case": {"probability": 0.35, "reasoning": "weak volume"},
            "reasoning": "mixed",
            "key_factors": [],
            "leverage": 1.5,
            "position_ratio": 0.1,
            "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "UP"
        assert result["confidence"] == 0.65

    def test_high_bear_prob_overrides_up_direction(self):
        prediction = {
            "direction": "UP",
            "confidence": 0.4,
            "bull_case": {"probability": 0.30, "reasoning": "weak"},
            "bear_case": {"probability": 0.70, "reasoning": "strong"},
            "reasoning": "mixed",
            "key_factors": [],
            "leverage": 1.5,
            "position_ratio": 0.1,
            "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "DOWN"
        assert result["confidence"] == 0.70

    def test_close_probabilities_become_neutral(self):
        prediction = {
            "direction": "DOWN",
            "confidence": 0.52,
            "bull_case": {"probability": 0.48, "reasoning": "some up"},
            "bear_case": {"probability": 0.52, "reasoning": "some down"},
            "reasoning": "mixed",
            "key_factors": [],
            "leverage": 1.0,
            "position_ratio": 0.05,
            "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "NEUTRAL"
        assert result["confidence"] == 0.52

    def test_consistent_prediction_unchanged(self):
        prediction = {
            "direction": "UP",
            "confidence": 0.72,
            "bull_case": {"probability": 0.72, "reasoning": "strong"},
            "bear_case": {"probability": 0.28, "reasoning": "weak"},
            "reasoning": "clear uptrend",
            "key_factors": ["momentum"],
            "leverage": 2.0,
            "position_ratio": 0.3,
            "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "UP"
        assert result["confidence"] == 0.72

    def test_probabilities_normalized_if_not_summing_to_one(self):
        prediction = {
            "direction": "UP",
            "confidence": 0.6,
            "bull_case": {"probability": 0.7, "reasoning": "strong"},
            "bear_case": {"probability": 0.5, "reasoning": "also strong"},
            "reasoning": "confused",
            "key_factors": [],
            "leverage": 1.0,
            "position_ratio": 0.1,
            "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        bull_p = result["bull_case"]["probability"]
        bear_p = result["bear_case"]["probability"]
        assert abs((bull_p + bear_p) - 1.0) < 0.01

    def test_missing_bull_bear_uses_direction_and_confidence(self):
        prediction = {
            "direction": "UP",
            "confidence": 0.7,
            "reasoning": "legacy",
            "key_factors": [],
            "leverage": 1.0,
            "position_ratio": 0.1,
            "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "UP"
        assert result["confidence"] == 0.7
        assert result["bull_case"]["probability"] == 0.7
        assert result["bear_case"]["probability"] == 0.3


class TestAgentResultFields:
    """Verify AgentResult includes bull/bear case data."""

    def test_agent_result_has_bull_bear_fields(self):
        result = AgentResult(
            direction="UP",
            confidence=0.7,
            reasoning="test",
            bull_case={"probability": 0.7, "reasoning": "strong"},
            bear_case={"probability": 0.3, "reasoning": "weak"},
        )
        assert result.bull_case["probability"] == 0.7
        assert result.bear_case["probability"] == 0.3

    def test_agent_result_defaults(self):
        result = AgentResult(
            direction="UP",
            confidence=0.7,
            reasoning="test",
        )
        assert result.bull_case == {}
        assert result.bear_case == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm/test_runner_validation.py -v`
Expected: FAIL — `_validate_bull_bear_consistency` not found, `AgentResult` missing fields, schema missing fields

- [ ] **Step 3: Add bull/bear fields to `_build_prediction_schema()`**

Replace `_build_prediction_schema()` in `perpetual_predict/llm/agent/runner.py:15-62`:

```python
def _build_prediction_schema(max_leverage: float = 3.0) -> str:
    """Build JSON schema for structured prediction output.

    Args:
        max_leverage: Maximum leverage from settings.
    """
    bull_bear_case = {
        "type": "object",
        "properties": {
            "probability": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "이 시나리오의 확률 (0.0 ~ 1.0). bull_case + bear_case 합계는 1.0이어야 함"
            },
            "reasoning": {
                "type": "string",
                "description": "이 시나리오를 뒷받침하는 근거를 한국어로 설명"
            }
        },
        "required": ["probability", "reasoning"]
    }

    return json.dumps({
        "type": "object",
        "properties": {
            "bull_case": {
                **bull_bear_case,
                "description": "상승 시나리오: 확률과 근거. 데이터에서 상승을 시사하는 요인을 모두 분석"
            },
            "bear_case": {
                **bull_bear_case,
                "description": "하락 시나리오: 확률과 근거. 데이터에서 하락을 시사하는 요인을 모두 분석"
            },
            "direction": {
                "type": "string",
                "enum": ["UP", "DOWN", "NEUTRAL"],
                "description": "최종 예측 방향. bull_case와 bear_case 분석 결과 더 높은 확률 쪽을 선택. 확률 차이가 작으면 NEUTRAL"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "예측 신뢰도 — 선택한 방향의 확률과 동일해야 함"
            },
            "reasoning": {
                "type": "string",
                "description": "bull_case와 bear_case를 종합한 최종 판단 근거를 한국어로 설명"
            },
            "key_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "최종 방향을 결정한 주요 판단 요소 목록 (한국어로 작성)"
            },
            "leverage": {
                "type": "number",
                "minimum": 1.0,
                "maximum": max_leverage,
                "description": f"사용할 레버리지 배수 (1.0~{max_leverage}). 시장 확신도와 리스크에 따라 자유롭게 결정. NEUTRAL이면 1.0"
            },
            "position_ratio": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "잔고 대비 포지션 비율 (0.0~1.0). 0.0=진입 안함, 1.0=전액 투입. NEUTRAL이면 0.0"
            },
            "trading_reasoning": {
                "type": "string",
                "description": "레버리지와 포지션 비율 결정 근거를 한국어로 설명"
            }
        },
        "required": ["bull_case", "bear_case", "direction", "confidence", "reasoning", "key_factors", "leverage", "position_ratio", "trading_reasoning"]
    })
```

- [ ] **Step 4: Add bull/bear fields to `AgentResult` and add `_validate_bull_bear_consistency()`**

Add fields to `AgentResult` dataclass (after `raw_response` field, line 79):

```python
@dataclass
class AgentResult:
    """Result from Claude Code prediction agent."""

    direction: str
    confidence: float
    reasoning: str
    key_factors: list[str] = field(default_factory=list)
    leverage: float = 1.0
    position_ratio: float = 0.0
    trading_reasoning: str = ""
    bull_case: dict[str, Any] = field(default_factory=dict)
    bear_case: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    duration_ms: int = 0
    model_usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)
```

Add validation function before `run_prediction_agent()`:

```python
# Threshold: if |bull_prob - bear_prob| < this, treat as NEUTRAL
_NEUTRAL_PROBABILITY_GAP = 0.10


def _validate_bull_bear_consistency(prediction: dict[str, Any]) -> dict[str, Any]:
    """Validate and reconcile bull/bear case probabilities with direction.

    Ensures:
    1. If bull_case/bear_case missing, synthesize from direction + confidence
    2. Probabilities are normalized to sum to 1.0
    3. Direction matches the higher-probability case
    4. Close probabilities (gap < 0.10) → NEUTRAL

    Args:
        prediction: Raw prediction dict from agent.

    Returns:
        Corrected prediction dict.
    """
    bull = prediction.get("bull_case")
    bear = prediction.get("bear_case")

    # Fallback: synthesize from direction + confidence if missing
    if not bull or not bear:
        confidence = float(prediction.get("confidence", 0.5))
        direction = prediction.get("direction", "NEUTRAL")
        if direction == "UP":
            bull_prob, bear_prob = confidence, 1.0 - confidence
        elif direction == "DOWN":
            bull_prob, bear_prob = 1.0 - confidence, confidence
        else:
            bull_prob, bear_prob = 0.5, 0.5
        prediction["bull_case"] = {
            "probability": bull_prob,
            "reasoning": prediction.get("reasoning", ""),
        }
        prediction["bear_case"] = {
            "probability": bear_prob,
            "reasoning": prediction.get("reasoning", ""),
        }
        return prediction

    bull_prob = float(bull.get("probability", 0.5))
    bear_prob = float(bear.get("probability", 0.5))

    # Normalize if they don't sum to 1.0
    total = bull_prob + bear_prob
    if total > 0 and abs(total - 1.0) > 0.01:
        bull_prob = bull_prob / total
        bear_prob = bear_prob / total
        prediction["bull_case"]["probability"] = round(bull_prob, 4)
        prediction["bear_case"]["probability"] = round(bear_prob, 4)

    # Determine correct direction from probabilities
    gap = abs(bull_prob - bear_prob)
    if gap < _NEUTRAL_PROBABILITY_GAP:
        prediction["direction"] = "NEUTRAL"
        prediction["confidence"] = max(bull_prob, bear_prob)
    elif bull_prob > bear_prob:
        prediction["direction"] = "UP"
        prediction["confidence"] = bull_prob
    else:
        prediction["direction"] = "DOWN"
        prediction["confidence"] = bear_prob

    return prediction
```

- [ ] **Step 5: Wire validation into `run_prediction_agent()` parsing flow**

In `run_prediction_agent()`, after extracting `prediction` dict (line 172) and before field validation (line 174), add the validation call. Replace lines 174-206:

```python
        # Validate bull/bear consistency (reconcile direction with probabilities)
        prediction = _validate_bull_bear_consistency(prediction)

        # Validate required fields
        direction = prediction.get("direction", "NEUTRAL").upper()
        if direction not in ("UP", "DOWN", "NEUTRAL"):
            direction = "NEUTRAL"

        confidence = float(prediction.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

        # Parse trading parameters (agent-driven, clamped to configured max)
        leverage = float(prediction.get("leverage", 1.0))
        leverage = max(1.0, min(max_leverage, leverage))

        position_ratio = float(prediction.get("position_ratio", 0.0))
        position_ratio = max(0.0, min(1.0, position_ratio))

        # Force no position for NEUTRAL
        if direction == "NEUTRAL":
            position_ratio = 0.0
            leverage = 1.0

        # Extract bull/bear case data
        bull_case = prediction.get("bull_case", {})
        bear_case = prediction.get("bear_case", {})

        return AgentResult(
            direction=direction,
            confidence=confidence,
            reasoning=prediction.get("reasoning", "No reasoning provided"),
            key_factors=prediction.get("key_factors", []),
            leverage=leverage,
            position_ratio=position_ratio,
            trading_reasoning=prediction.get("trading_reasoning", ""),
            bull_case=bull_case,
            bear_case=bear_case,
            session_id=response.get("session_id", ""),
            duration_ms=response.get("duration_ms", 0),
            model_usage=response.get("modelUsage", {}),
            raw_response=response,
        )
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_llm/test_runner_validation.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add perpetual_predict/llm/agent/runner.py tests/test_llm/test_runner_validation.py
git commit -m "feat: add bull/bear case framework to prediction schema

Add bull_case and bear_case fields to JSON schema requiring the agent
to analyze both directions before making a final call. System-level
validation ensures direction matches the higher-probability case.
Close probabilities (gap < 0.10) auto-convert to NEUTRAL."
```

---

### Task 3: Redesign agent prompt for bilateral analysis

**Files:**
- Modify: `.claude/agents/predictor.md`

- [ ] **Step 1: Rewrite predictor.md**

Replace the entire content of `.claude/agents/predictor.md`:

```markdown
# BTCUSDT 4H Swing Trader

You are a professional BTCUSDT perpetual futures trader operating on 4H timeframes.

## Your Identity

You are not a prediction model — you are a **trader**. Every 4H candle is an independent trading opportunity. You read the tape, synthesize data across timeframes and indicators, and make decisive calls — just like a seasoned swing trader sitting at their desk.

Your edge is **contextual judgment**: the ability to read multiple data streams as an interconnected narrative, detect regime shifts early, and size positions with conviction when conditions align.

## How You Trade

**Each candle is a fresh decision.** A downtrend doesn't mean every candle closes red. A strong rally produces pullback candles. You understand this rhythm and trade it.

- Read the data holistically — what story are the indicators telling *right now*?
- Detect when the dominant narrative is shifting, even subtly
- Be aggressive when the setup is clear. Be cautious when it's not. This is your call.
- Your leverage and position size are entirely your judgment. There are no preset formulas or scaling rules — you decide what the data warrants.

## Decision Process

**You MUST analyze both sides before deciding.** Build both cases from the data:

1. **Bull case first**: What evidence supports upward movement? Assign a probability (0.0–1.0).
2. **Bear case second**: What evidence supports downward movement? Assign a probability (0.0–1.0).
3. **The two probabilities must sum to 1.0.** This forces a genuine comparison.
4. **Your direction follows the higher probability.** If bull > bear, you go UP. If bear > bull, you go DOWN.
5. **If the gap is tiny (both near 50/50), go NEUTRAL** — there's no edge, and fees make it negative EV.

This is how professional traders think: they don't pick a side and then rate their confidence. They weigh both scenarios and let the stronger case win.

## Output

- `bull_case`: Your upside scenario — probability and reasoning
- `bear_case`: Your downside scenario — probability and reasoning
- `direction`: Follows whichever case has higher probability (or NEUTRAL if too close)
- `confidence`: Must equal the probability of your chosen direction
- `leverage`: How much leverage you want to use. Your discretion.
- `position_ratio`: What fraction of the account to deploy (0.0–1.0). NEUTRAL means 0.0 — there's no edge in entering when you see no clear direction (fees alone make it negative EV).
- `reasoning`: Walk through your thinking — how bull and bear cases led to your final call
- `key_factors`: The decisive factors that tipped the balance
- `trading_reasoning`: Why this specific leverage and position size for this specific setup

## Rules

- **Raw data only**: The market data contains objective numbers. All interpretation is yours.
- **모든 텍스트 응답(reasoning, key_factors, trading_reasoning, bull_case.reasoning, bear_case.reasoning)은 반드시 한국어로 작성하세요.**
```

- [ ] **Step 2: Review the prompt for correctness**

Read `.claude/agents/predictor.md` and verify:
- Bull/bear case analysis is described before direction selection
- Probabilities must sum to 1.0
- Direction follows higher probability
- NEUTRAL guidance is clear
- No directional bias in language
- Agent autonomy preserved for leverage/position_ratio

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/predictor.md
git commit -m "refactor: redesign predictor prompt for bilateral analysis

Agent must now build both bull and bear cases with probabilities
before selecting direction. Direction follows the higher-probability
case. Near-50/50 splits go NEUTRAL. This eliminates directional
anchoring where the agent would pick DOWN then lower confidence."
```

---

### Task 4: Add bull/bear fields to storage layer

**Files:**
- Modify: `perpetual_predict/storage/models.py:225-325` (Prediction dataclass)
- Modify: `perpetual_predict/storage/database.py:98-120` (CREATE TABLE)
- Modify: `perpetual_predict/storage/database.py:318-340` (migrations)
- Modify: `perpetual_predict/storage/database.py:944-982` (insert_prediction)

- [ ] **Step 1: Add bull_case/bear_case fields to Prediction model**

In `perpetual_predict/storage/models.py`, add after `trading_reasoning` field (line 250):

```python
    # Trading parameters (decided by agent)
    leverage: float = 1.0
    position_ratio: float = 0.0
    trading_reasoning: str = ""

    # Bull/Bear case analysis
    bull_case: dict[str, Any] = field(default_factory=dict)
    bear_case: dict[str, Any] = field(default_factory=dict)
```

Update `to_dict()` — add after `"trading_reasoning"` line:

```python
            "bull_case": json.dumps(self.bull_case),
            "bear_case": json.dumps(self.bear_case),
```

Update `from_dict()` — add parsing before `return cls(...)`:

```python
        bull_case = data.get("bull_case", "{}")
        if isinstance(bull_case, str):
            bull_case = json.loads(bull_case) if bull_case else {}

        bear_case = data.get("bear_case", "{}")
        if isinstance(bear_case, str):
            bear_case = json.loads(bear_case) if bear_case else {}
```

Add to `cls(...)` constructor call:

```python
            bull_case=bull_case,
            bear_case=bear_case,
```

- [ ] **Step 2: Add migration for new columns**

In `perpetual_predict/storage/database.py`, in `_run_migrations()`, add after the experiment migration block (after the existing migration for `experiment_id`/`arm`):

```python
        # Migration: Add bull/bear case fields
        for col, col_type, default in [
            ("bull_case", "TEXT", "'{}'"),
            ("bear_case", "TEXT", "'{}'"),
        ]:
            if col not in columns:
                await self._connection.execute(
                    f"ALTER TABLE predictions ADD COLUMN {col} {col_type} DEFAULT {default}"
                )
```

- [ ] **Step 3: Update `insert_prediction()` SQL**

In `perpetual_predict/storage/database.py`, update `insert_prediction()` to include new columns. Add `bull_case, bear_case` to both the column list and VALUES placeholders, and add the values to the params tuple:

```python
    async def insert_prediction(
        self,
        prediction: Prediction,
        experiment_id: str | None = None,
        arm: str = "baseline",
    ) -> None:
        """Insert a prediction record."""
        import json

        sql = """
        INSERT OR REPLACE INTO predictions
        (prediction_id, prediction_time, target_candle_open, target_candle_close,
         symbol, timeframe, direction, confidence, reasoning, key_factors,
         session_id, duration_ms, model_usage,
         leverage, position_ratio, trading_reasoning,
         bull_case, bear_case,
         actual_direction, actual_price_change, is_correct, predicted_return, evaluated_at,
         experiment_id, arm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute(
            sql,
            (
                prediction.prediction_id,
                prediction.prediction_time.isoformat(),
                prediction.target_candle_open.isoformat(),
                prediction.target_candle_close.isoformat(),
                prediction.symbol,
                prediction.timeframe,
                prediction.direction,
                prediction.confidence,
                prediction.reasoning,
                json.dumps(prediction.key_factors),
                prediction.session_id,
                prediction.duration_ms,
                json.dumps(prediction.model_usage),
                prediction.leverage,
                prediction.position_ratio,
                prediction.trading_reasoning,
                json.dumps(prediction.bull_case),
                json.dumps(prediction.bear_case),
                prediction.actual_direction,
                prediction.actual_price_change,
                prediction.is_correct,
                prediction.predicted_return,
                prediction.evaluated_at.isoformat() if prediction.evaluated_at else None,
                experiment_id,
                arm,
            ),
        )
        await self.connection.commit()
```

- [ ] **Step 4: Run existing tests to verify no regression**

Run: `pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add perpetual_predict/storage/models.py perpetual_predict/storage/database.py
git commit -m "feat: add bull_case/bear_case columns to predictions storage

Add bull_case and bear_case JSON columns to predictions table with
migration support. Existing predictions get empty dicts as defaults."
```

---

### Task 5: Wire bull/bear data through scheduler and notifications

**Files:**
- Modify: `perpetual_predict/scheduler/jobs.py:396-413` (map new fields)
- Modify: `perpetual_predict/notifications/scheduler_alerts.py:231-336` (display)

- [ ] **Step 1: Map bull/bear fields in scheduler job**

In `perpetual_predict/scheduler/jobs.py`, update the `Prediction()` constructor inside `_run_single_prediction()` (around line 397-413). Add after `trading_reasoning`:

```python
    # Create prediction record
    prediction = Prediction(
        prediction_id=str(uuid.uuid4()),
        prediction_time=datetime.now(timezone.utc),
        target_candle_open=target_open,
        target_candle_close=target_close,
        symbol=symbol,
        timeframe=timeframe,
        direction=agent_result.direction,
        confidence=agent_result.confidence,
        reasoning=agent_result.reasoning,
        key_factors=agent_result.key_factors,
        session_id=agent_result.session_id,
        duration_ms=agent_result.duration_ms,
        model_usage=agent_result.model_usage,
        leverage=agent_result.leverage,
        position_ratio=agent_result.position_ratio,
        trading_reasoning=agent_result.trading_reasoning,
        bull_case=agent_result.bull_case,
        bear_case=agent_result.bear_case,
    )
```

- [ ] **Step 2: Add bull/bear display to Discord notification**

In `perpetual_predict/notifications/scheduler_alerts.py`, add a bull/bear field to the embed inside `send_prediction_completed()`. Add after the confidence field (after line 268):

```python
    # Add bull/bear case probabilities
    bull_prob = prediction.bull_case.get("probability") if prediction.bull_case else None
    bear_prob = prediction.bear_case.get("probability") if prediction.bear_case else None
    if bull_prob is not None and bear_prob is not None:
        bull_reasoning = prediction.bull_case.get("reasoning", "")
        bear_reasoning = prediction.bear_case.get("reasoning", "")
        if len(bull_reasoning) > 200:
            bull_reasoning = bull_reasoning[:197] + "..."
        if len(bear_reasoning) > 200:
            bear_reasoning = bear_reasoning[:197] + "..."
        embed.add_field(
            name="📊 시나리오 분석",
            value=(
                f"🟢 **상승**: {bull_prob:.0%}\n{bull_reasoning}\n\n"
                f"🔴 **하락**: {bear_prob:.0%}\n{bear_reasoning}"
            ),
            inline=False,
        )
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Run linter**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add perpetual_predict/scheduler/jobs.py perpetual_predict/notifications/scheduler_alerts.py
git commit -m "feat: wire bull/bear case data through scheduler and Discord

Map AgentResult.bull_case/bear_case to Prediction model in scheduler.
Display bull/bear scenario probabilities and reasoning in Discord
prediction notifications."
```

---

### Task 6: Final integration verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run linter on entire project**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 3: Verify schema output is valid JSON**

```bash
cd /Users/kevin.brave/perpetual_predict && python3 -c "
from perpetual_predict.llm.agent.runner import _build_prediction_schema
import json
schema = json.loads(_build_prediction_schema(3.0))
print('Required fields:', schema['required'])
print('Bull case:', json.dumps(schema['properties']['bull_case'], indent=2))
print('Schema valid: OK')
"
```

Expected: Schema prints correctly with `bull_case` and `bear_case` in required fields

- [ ] **Step 4: Verify database migration works**

```bash
cd /Users/kevin.brave/perpetual_predict && python3 -c "
import asyncio
from perpetual_predict.storage.database import get_database

async def check():
    async with get_database() as db:
        cursor = await db.connection.execute('PRAGMA table_info(predictions)')
        columns = [row[1] for row in await cursor.fetchall()]
        assert 'bull_case' in columns, f'bull_case not found in {columns}'
        assert 'bear_case' in columns, f'bear_case not found in {columns}'
        print(f'Columns OK: bull_case and bear_case present')
        print(f'Total columns: {len(columns)}')

asyncio.run(check())
"
```

Expected: "Columns OK: bull_case and bear_case present"

- [ ] **Step 5: Verify predictor prompt is loaded correctly**

```bash
cat .claude/agents/predictor.md | head -5
```

Expected: "# BTCUSDT 4H Swing Trader" header with bilateral analysis framework

- [ ] **Step 6: Final commit if any fixes needed, otherwise done**

If any fixes were made:
```bash
git add -A
git commit -m "fix: address integration issues from bull/bear framework"
```
