"""Statistical analysis for A/B testing experiments."""

from __future__ import annotations

import math

from perpetual_predict.experiment.models import ExperimentResult, VariantResult
from perpetual_predict.storage.database import Database
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


class ExperimentAnalyzer:
    """Analyzes experiment results with statistical tests."""

    def __init__(self, db: Database):
        self.db = db

    async def analyze(self, experiment_id: str) -> ExperimentResult | None:
        """Run full analysis on an experiment (multi-variant)."""
        experiment = await self.db.get_experiment(experiment_id)
        if not experiment:
            return None

        # Control arm data
        control_preds = await self.db.get_predictions_by_experiment(
            experiment_id, "control", evaluated_only=True,
        )
        control_trades = await self.db.get_paper_trades_by_experiment(
            experiment_id, "control",
        )

        control_correct = sum(1 for p in control_preds if p.is_correct)
        control_accuracy = control_correct / len(control_preds) if control_preds else 0
        control_returns = [t.return_pct for t in control_trades if t.return_pct is not None]
        control_return = sum(control_returns)
        control_sharpe = _sharpe_ratio(control_returns)

        # Analyze each variant
        variant_results = []
        for variant_name in experiment.variants:
            arm = f"variant_{variant_name}"

            variant_preds = await self.db.get_predictions_by_experiment(
                experiment_id, arm, evaluated_only=True,
            )
            variant_trades = await self.db.get_paper_trades_by_experiment(
                experiment_id, arm,
            )

            variant_correct = sum(1 for p in variant_preds if p.is_correct)
            variant_accuracy = variant_correct / len(variant_preds) if variant_preds else 0
            variant_returns = [t.return_pct for t in variant_trades if t.return_pct is not None]
            variant_return_total = sum(variant_returns)
            variant_sharpe = _sharpe_ratio(variant_returns)

            sample_size = min(len(control_preds), len(variant_preds))

            # Statistical test
            p_value = None
            is_significant = False

            if sample_size >= experiment.min_samples:
                metric = experiment.primary_metric
                if metric == "accuracy":
                    p_value = _proportions_z_test(
                        control_correct, len(control_preds),
                        variant_correct, len(variant_preds),
                    )
                elif metric == "net_return" and control_returns and variant_returns:
                    p_value = _welch_t_test(control_returns, variant_returns)
                elif metric == "sharpe" and control_returns and variant_returns:
                    p_value = _welch_t_test(control_returns, variant_returns)

                if p_value is not None:
                    is_significant = p_value < experiment.significance_level

            variant_results.append(VariantResult(
                variant_name=variant_name,
                sample_size=sample_size,
                accuracy=variant_accuracy,
                net_return=variant_return_total,
                sharpe=variant_sharpe,
                p_value=p_value,
                is_significant=is_significant,
            ))

        return ExperimentResult(
            experiment_id=experiment_id,
            control_accuracy=control_accuracy,
            control_return=control_return,
            control_sharpe=control_sharpe,
            control_sample_size=len(control_preds),
            variant_results=variant_results,
        )


def _sharpe_ratio(returns: list[float], risk_free: float = 0.0) -> float:
    """Calculate annualized Sharpe ratio from per-trade returns."""
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns) - risk_free
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0001
    # Annualize: ~6 trades/day (4H) * 365
    return (mean / std) * math.sqrt(6 * 365)


def _proportions_z_test(
    x1: int, n1: int, x2: int, n2: int,
) -> float:
    """Two-proportion z-test. Returns p-value."""
    if n1 == 0 or n2 == 0:
        return 1.0
    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0

    z = abs(p1 - p2) / se
    # Approximate two-tailed p-value using normal CDF
    return 2 * (1 - _norm_cdf(z))


def _welch_t_test(a: list[float], b: list[float]) -> float:
    """Welch's t-test. Returns p-value."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 1.0

    mean1 = sum(a) / n1
    mean2 = sum(b) / n2
    var1 = sum((x - mean1) ** 2 for x in a) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in b) / (n2 - 1)

    se = math.sqrt(var1 / n1 + var2 / n2)
    if se == 0:
        return 1.0

    t = abs(mean1 - mean2) / se

    # Welch-Satterthwaite degrees of freedom
    num = (var1 / n1 + var2 / n2) ** 2
    denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    df = num / denom if denom > 0 else 1

    # Approximate p-value using normal for large df, else conservative
    if df > 30:
        return 2 * (1 - _norm_cdf(t))
    # For small df, use more conservative approximation
    return 2 * (1 - _norm_cdf(t * math.sqrt(df / (df + t * t))))


def _norm_cdf(x: float) -> float:
    """Approximate standard normal CDF (Abramowitz & Stegun)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
