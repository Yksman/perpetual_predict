"""Tests for multi-variant experiment analyzer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from perpetual_predict.experiment.analyzer import ExperimentAnalyzer
from perpetual_predict.experiment.models import DEFAULT_MODULES, Experiment


def _make_experiment(variants_count=2):
    variants = {}
    if variants_count >= 1:
        variants["macro"] = [*DEFAULT_MODULES, "macro"]
    if variants_count >= 2:
        variants["news"] = [*DEFAULT_MODULES, "news"]
    return Experiment(
        experiment_id="exp_test",
        name="test",
        variants=variants,
        min_samples=5,
        significance_level=0.05,
        primary_metric="net_return",
    )


def _make_predictions(count, correct_ratio=0.5):
    preds = []
    for i in range(count):
        p = MagicMock()
        p.is_correct = i < int(count * correct_ratio)
        preds.append(p)
    return preds


def _make_trades(count, return_pct=1.0):
    trades = []
    for _ in range(count):
        t = MagicMock()
        t.return_pct = return_pct
        trades.append(t)
    return trades


class TestMultiVariantAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_returns_result_per_variant(self):
        db = AsyncMock()
        db.get_experiment = AsyncMock(return_value=_make_experiment(2))
        db.get_predictions_by_experiment = AsyncMock(
            side_effect=lambda eid, arm, **kw: _make_predictions(10, 0.5)
        )
        db.get_paper_trades_by_experiment = AsyncMock(
            side_effect=lambda eid, arm, **kw: _make_trades(10, 1.0)
        )

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze("exp_test")

        assert result is not None
        assert len(result.variant_results) == 2
        assert result.variant_results[0].variant_name == "macro"
        assert result.variant_results[1].variant_name == "news"

    @pytest.mark.asyncio
    async def test_analyze_not_found(self):
        db = AsyncMock()
        db.get_experiment = AsyncMock(return_value=None)

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_single_variant_compat(self):
        exp = Experiment(
            experiment_id="exp_old",
            name="old",
            variants={"variant": [*DEFAULT_MODULES, "macro"]},
            min_samples=5,
        )
        db = AsyncMock()
        db.get_experiment = AsyncMock(return_value=exp)
        db.get_predictions_by_experiment = AsyncMock(
            side_effect=lambda eid, arm, **kw: _make_predictions(10, 0.6)
        )
        db.get_paper_trades_by_experiment = AsyncMock(
            side_effect=lambda eid, arm, **kw: _make_trades(10, 2.0)
        )

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze("exp_old")

        assert result is not None
        assert len(result.variant_results) == 1
        assert result.variant_accuracy > 0
