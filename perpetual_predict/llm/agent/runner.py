"""Claude Code CLI runner for predictions."""

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


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
            "position_pct": {
                "type": "number",
                "minimum": 0.0,
                "maximum": max_leverage,
                "description": f"투자금 대비 진입 비율 (0.0~{max_leverage}). "
                               f"1.0=투자금 100%, 1.5=투자금 150%(레버리지 1.5x), "
                               f"2.0=투자금 200%(레버리지 2x). "
                               f"NEUTRAL이면 0.0. 시장 확신도에 따라 자유롭게 결정"
            },
            "trading_reasoning": {
                "type": "string",
                "description": "레버리지와 포지션 비율 결정 근거를 한국어로 설명"
            }
        },
        "required": ["bull_case", "bear_case", "direction", "confidence", "reasoning", "key_factors", "position_pct", "trading_reasoning"]
    })


@dataclass
class AgentResult:
    """Result from Claude Code prediction agent."""

    direction: str
    confidence: float
    reasoning: str
    key_factors: list[str] = field(default_factory=list)
    position_pct: float = 0.0
    trading_reasoning: str = ""
    bull_case: dict[str, Any] = field(default_factory=dict)
    bear_case: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    duration_ms: int = 0
    model_usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


class ClaudeAgentError(Exception):
    """Error running Claude Code agent."""
    pass


_NEUTRAL_PROBABILITY_GAP = 0.10


def _validate_bull_bear_consistency(prediction: dict[str, Any]) -> dict[str, Any]:
    """Validate and reconcile bull/bear case probabilities with direction.

    Ensures:
    1. If bull_case/bear_case missing, synthesize from direction + confidence
    2. Probabilities are normalized to sum to 1.0
    3. Direction matches the higher-probability case
    4. Close probabilities (gap < 0.10) -> NEUTRAL
    """
    bull = prediction.get("bull_case")
    bear = prediction.get("bear_case")

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
            "probability": round(bull_prob, 4),
            "reasoning": prediction.get("reasoning", ""),
        }
        prediction["bear_case"] = {
            "probability": round(bear_prob, 4),
            "reasoning": prediction.get("reasoning", ""),
        }
        return prediction

    bull_prob = float(bull.get("probability", 0.5))
    bear_prob = float(bear.get("probability", 0.5))

    total = bull_prob + bear_prob
    if total > 0 and abs(total - 1.0) > 0.01:
        bull_prob = bull_prob / total
        bear_prob = bear_prob / total
        prediction["bull_case"]["probability"] = round(bull_prob, 4)
        prediction["bear_case"]["probability"] = round(bear_prob, 4)

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


async def run_prediction_agent(
    market_context: str,
    timeout_seconds: int = 300,
    working_dir: Path | None = None,
) -> AgentResult:
    """Run Claude Code prediction agent in headless mode.

    Args:
        market_context: Formatted market data prompt
        timeout_seconds: Maximum execution time
        working_dir: Working directory for Claude CLI (defaults to project root)

    Returns:
        AgentResult with prediction details

    Raises:
        ClaudeAgentError: If agent execution fails
    """
    from perpetual_predict.config.settings import get_settings

    settings = get_settings()
    max_leverage = settings.paper_trading.max_leverage

    if working_dir is None:
        # Default to llm-analysis directory
        working_dir = Path(__file__).parent.parent.parent.parent

    # Build command with dynamic schema
    prediction_schema = _build_prediction_schema(max_leverage)
    cmd = [
        "claude",
        "-p",  # headless/print mode
        "--agent", "predictor",
        "--output-format", "json",
        "--json-schema", prediction_schema,
        market_context,
    ]

    logger.info("Running Claude prediction agent...")
    logger.debug(f"Working directory: {working_dir}")

    try:
        # Run in thread pool to avoid blocking
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=working_dir,
            )
        )

        if result.returncode != 0:
            logger.error(f"Claude CLI failed: {result.stderr}")
            raise ClaudeAgentError(f"Claude CLI exit code {result.returncode}: {result.stderr}")

        # Parse JSON response
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {result.stdout[:500]}")
            raise ClaudeAgentError(f"Invalid JSON response: {e}")

        # Check for error in response
        if response.get("is_error"):
            raise ClaudeAgentError(f"Claude returned error: {response.get('result', 'Unknown error')}")

        # Extract prediction from structured_output (preferred) or result
        prediction = response.get("structured_output")

        if prediction and isinstance(prediction, dict):
            # structured_output contains the JSON directly
            logger.info("Using structured_output from Claude CLI")
        else:
            # Fallback to parsing result field
            prediction_text = response.get("result", "")
            try:
                # Sometimes the result is wrapped in markdown code blocks
                prediction_text = _extract_json(prediction_text)
                prediction = json.loads(prediction_text)
            except json.JSONDecodeError:
                # If not valid JSON, try to extract from text
                logger.warning("Could not parse prediction as JSON, attempting extraction")
                prediction = _extract_prediction_from_text(prediction_text)

        # Validate bull/bear consistency (reconcile direction with probabilities)
        prediction = _validate_bull_bear_consistency(prediction)

        # Validate required fields
        direction = prediction.get("direction", "NEUTRAL").upper()
        if direction not in ("UP", "DOWN", "NEUTRAL"):
            direction = "NEUTRAL"

        confidence = float(prediction.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

        # Parse trading parameters (agent-driven, clamped to configured max)
        position_pct = float(prediction.get("position_pct", 0.0))
        position_pct = max(0.0, min(max_leverage, position_pct))

        # Force no position for NEUTRAL
        if direction == "NEUTRAL":
            position_pct = 0.0

        return AgentResult(
            direction=direction,
            confidence=confidence,
            reasoning=prediction.get("reasoning", "No reasoning provided"),
            key_factors=prediction.get("key_factors", []),
            position_pct=position_pct,
            trading_reasoning=prediction.get("trading_reasoning", ""),
            bull_case=prediction.get("bull_case", {}),
            bear_case=prediction.get("bear_case", {}),
            session_id=response.get("session_id", ""),
            duration_ms=response.get("duration_ms", 0),
            model_usage=response.get("modelUsage", {}),
            raw_response=response,
        )

    except subprocess.TimeoutExpired:
        raise ClaudeAgentError(f"Claude CLI timed out after {timeout_seconds}s")
    except FileNotFoundError:
        raise ClaudeAgentError("Claude CLI not found. Ensure 'claude' is in PATH")


def _extract_json(text: str) -> str:
    """Extract JSON from text that may be wrapped in markdown code blocks."""
    text = text.strip()

    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def _extract_prediction_from_text(text: str) -> dict[str, Any]:
    """Attempt to extract prediction data from unstructured text."""
    result = {
        "direction": "NEUTRAL",
        "confidence": 0.5,
        "reasoning": text[:500] if text else "Unable to parse prediction",
        "key_factors": [],
        "position_pct": 0.0,
        "trading_reasoning": "",
    }

    text_lower = text.lower()

    # Try to find direction
    if "direction" in text_lower:
        if '"up"' in text_lower or "'up'" in text_lower:
            result["direction"] = "UP"
        elif '"down"' in text_lower or "'down'" in text_lower:
            result["direction"] = "DOWN"
    else:
        # Simple heuristic based on keywords
        bullish_words = ["bullish", "upward", "increase", "rise", "buy", "long"]
        bearish_words = ["bearish", "downward", "decrease", "fall", "sell", "short"]

        bullish_count = sum(1 for w in bullish_words if w in text_lower)
        bearish_count = sum(1 for w in bearish_words if w in text_lower)

        if bullish_count > bearish_count:
            result["direction"] = "UP"
        elif bearish_count > bullish_count:
            result["direction"] = "DOWN"

    # Try to find confidence
    import re
    confidence_match = re.search(r'"confidence":\s*([\d.]+)', text)
    if confidence_match:
        try:
            result["confidence"] = float(confidence_match.group(1))
        except ValueError:
            pass

    return result


# Convenience function for testing
async def test_agent() -> None:
    """Test the prediction agent with sample data."""
    sample_context = """
    ## BTCUSDT 4H Market Data

    ### Current Price
    - Price: $67,234.50
    - 24H Change: +2.3%
    - 4H Change: +0.8%

    ### Technical Indicators
    - RSI (14): 65
    - MACD: Positive, histogram increasing
    - SMA 20: $66,500 (price above)
    - SMA 50: $65,000 (price above)

    ### Market Sentiment
    - Funding Rate: 0.01%
    - Long/Short Ratio: 1.2
    - Fear & Greed: 68 (Greed)

    Based on this data, predict the direction of the current 4H candle (just started).
    """

    result = await run_prediction_agent(sample_context)
    print(f"Direction: {result.direction}")
    print(f"Confidence: {result.confidence}")
    print(f"Reasoning: {result.reasoning}")
    print(f"Key Factors: {result.key_factors}")


if __name__ == "__main__":
    asyncio.run(test_agent())
