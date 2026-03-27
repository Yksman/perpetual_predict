"""Tests for bull/bear case validation in prediction runner."""

import json

from perpetual_predict.llm.agent.runner import (
    AgentResult,
    _build_prediction_schema,
    _validate_bull_bear_consistency,
)


class TestPredictionSchema:

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

    def test_high_bull_prob_overrides_down_direction(self):
        prediction = {
            "direction": "DOWN", "confidence": 0.4,
            "bull_case": {"probability": 0.65, "reasoning": "strong momentum"},
            "bear_case": {"probability": 0.35, "reasoning": "weak volume"},
            "reasoning": "mixed", "key_factors": [],
            "leverage": 1.5, "position_ratio": 0.1, "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "UP"
        assert result["confidence"] == 0.65

    def test_high_bear_prob_overrides_up_direction(self):
        prediction = {
            "direction": "UP", "confidence": 0.4,
            "bull_case": {"probability": 0.30, "reasoning": "weak"},
            "bear_case": {"probability": 0.70, "reasoning": "strong"},
            "reasoning": "mixed", "key_factors": [],
            "leverage": 1.5, "position_ratio": 0.1, "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "DOWN"
        assert result["confidence"] == 0.70

    def test_close_probabilities_become_neutral(self):
        prediction = {
            "direction": "DOWN", "confidence": 0.52,
            "bull_case": {"probability": 0.48, "reasoning": "some up"},
            "bear_case": {"probability": 0.52, "reasoning": "some down"},
            "reasoning": "mixed", "key_factors": [],
            "leverage": 1.0, "position_ratio": 0.05, "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "NEUTRAL"
        assert result["confidence"] == 0.52

    def test_consistent_prediction_unchanged(self):
        prediction = {
            "direction": "UP", "confidence": 0.72,
            "bull_case": {"probability": 0.72, "reasoning": "strong"},
            "bear_case": {"probability": 0.28, "reasoning": "weak"},
            "reasoning": "clear uptrend", "key_factors": ["momentum"],
            "leverage": 2.0, "position_ratio": 0.3, "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "UP"
        assert result["confidence"] == 0.72

    def test_probabilities_normalized_if_not_summing_to_one(self):
        prediction = {
            "direction": "UP", "confidence": 0.6,
            "bull_case": {"probability": 0.7, "reasoning": "strong"},
            "bear_case": {"probability": 0.5, "reasoning": "also strong"},
            "reasoning": "confused", "key_factors": [],
            "leverage": 1.0, "position_ratio": 0.1, "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        bull_p = result["bull_case"]["probability"]
        bear_p = result["bear_case"]["probability"]
        assert abs((bull_p + bear_p) - 1.0) < 0.01

    def test_missing_bull_bear_uses_direction_and_confidence(self):
        prediction = {
            "direction": "UP", "confidence": 0.7,
            "reasoning": "legacy", "key_factors": [],
            "leverage": 1.0, "position_ratio": 0.1, "trading_reasoning": "test",
        }
        result = _validate_bull_bear_consistency(prediction)
        assert result["direction"] == "UP"
        assert result["confidence"] == 0.7
        assert result["bull_case"]["probability"] == 0.7
        assert result["bear_case"]["probability"] == 0.3


class TestAgentResultFields:

    def test_agent_result_has_bull_bear_fields(self):
        result = AgentResult(
            direction="UP", confidence=0.7, reasoning="test",
            bull_case={"probability": 0.7, "reasoning": "strong"},
            bear_case={"probability": 0.3, "reasoning": "weak"},
        )
        assert result.bull_case["probability"] == 0.7
        assert result.bear_case["probability"] == 0.3

    def test_agent_result_defaults(self):
        result = AgentResult(direction="UP", confidence=0.7, reasoning="test")
        assert result.bull_case == {}
        assert result.bear_case == {}
