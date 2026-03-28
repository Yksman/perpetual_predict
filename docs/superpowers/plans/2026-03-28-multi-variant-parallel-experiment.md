# Multi-Variant Parallel Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the A/B testing framework to support multiple variant arms per experiment with parallel predictor execution (max 4 concurrent).

**Architecture:** Experiment model changes from single `variant_modules: list[str]` to `variants: dict[str, list[str]]`. The prediction loop in jobs.py changes from sequential with 10s cooldown to `asyncio.gather()` with batched concurrency. CLI uses `--variant` flag. Analyzer loops over each variant for 1:1 comparison against control.

**Tech Stack:** asyncio (parallel execution), existing experiment framework, existing `claude -p` subprocess pattern

**Spec:** `docs/superpowers/specs/2026-03-28-multi-variant-parallel-experiment-design.md`

---

### Task 1: Experiment model — variant_modules → variants dict

**Files:**
- Modify: `perpetual_predict/experiment/models.py`
- Create: `tests/test_experiment/__init__.py`
- Create: `tests/test_experiment/test_experiment_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_experiment/__init__.py` (empty).

Create `tests/test_experiment/test_experiment_models.py`:

```python
"""Tests for multi-variant Experiment model."""

import json
from datetime import datetime, timezone

from perpetual_predict.experiment.models import DEFAULT_MODULES, Experiment


class TestExperimentVariants:
    """Tests for multi-variant experiment model."""

    def test_create_with_variants_dict(self):
        exp = Experiment(
            experiment_id="exp_test1",
            name="test",
            variants={
                "macro": [*DEFAULT_MODULES, "macro"],
                "news": [*DEFAULT_MODULES, "news"],
            },
        )
        assert len(exp.variants) == 2
        assert "macro" in exp.variants
        assert "news" in exp.variants

    def test_to_dict_serializes_variants_as_json(self):
        exp = Experiment(
            experiment_id="exp_test2",
            name="test",
            variants={
                "macro": [*DEFAULT_MODULES, "macro"],
            },
        )
        d = exp.to_dict()
        # variant_modules column stores the variants dict as JSON
        parsed = json.loads(d["variant_modules"])
        assert isinstance(parsed, dict)
        assert "macro" in parsed

    def test_from_dict_with_new_dict_format(self):
        variants = {
            "macro": [*DEFAULT_MODULES, "macro"],
            "news": [*DEFAULT_MODULES, "news"],
        }
        data = {
            "experiment_id": "exp_test3",
            "name": "test",
            "control_modules": json.dumps(list(DEFAULT_MODULES)),
            "variant_modules": json.dumps(variants),
        }
        exp = Experiment.from_dict(data)
        assert isinstance(exp.variants, dict)
        assert len(exp.variants) == 2
        assert "macro" in exp.variants

    def test_from_dict_backward_compat_with_list(self):
        """Old experiments stored variant_modules as a list. Should auto-convert."""
        old_modules = [*DEFAULT_MODULES, "macro"]
        data = {
            "experiment_id": "exp_old",
            "name": "legacy",
            "control_modules": json.dumps(list(DEFAULT_MODULES)),
            "variant_modules": json.dumps(old_modules),
        }
        exp = Experiment.from_dict(data)
        assert isinstance(exp.variants, dict)
        assert "variant" in exp.variants
        assert exp.variants["variant"] == old_modules

    def test_roundtrip(self):
        original = Experiment(
            experiment_id="exp_rt",
            name="roundtrip",
            variants={
                "macro": [*DEFAULT_MODULES, "macro"],
                "news": [*DEFAULT_MODULES, "news"],
                "macro_news": [*DEFAULT_MODULES, "macro", "news"],
            },
            created_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
        )
        restored = Experiment.from_dict(original.to_dict())
        assert restored.variants == original.variants
        assert len(restored.variants) == 3

    def test_variant_modules_property_compat(self):
        """variant_modules property returns first variant for backward compat."""
        exp = Experiment(
            experiment_id="exp_compat",
            name="compat",
            variants={"macro": [*DEFAULT_MODULES, "macro"]},
        )
        assert exp.variant_modules == [*DEFAULT_MODULES, "macro"]

    def test_variant_modules_property_empty(self):
        exp = Experiment(
            experiment_id="exp_empty",
            name="empty",
            variants={},
        )
        assert exp.variant_modules == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_experiment/test_experiment_models.py -v`
Expected: TypeError or AttributeError — Experiment has no `variants` parameter

- [ ] **Step 3: Implement model changes**

In `perpetual_predict/experiment/models.py`, modify the `Experiment` dataclass:

Replace `variant_modules` field (line 46) with:

```python
    variants: dict[str, list[str]] = field(default_factory=dict)
```

Add a backward-compat property after `winner` (after line 52):

```python
    @property
    def variant_modules(self) -> list[str]:
        """Backward compat: return first variant's modules."""
        if not self.variants:
            return []
        return next(iter(self.variants.values()))
```

Update `to_dict()` — change the variant_modules line (line 61):

```python
            "variant_modules": json.dumps(self.variants),
```

Update `from_dict()` — change the variant_modules parsing (lines 76-78):

```python
        variant_data = data.get("variant_modules", "{}")
        if isinstance(variant_data, str):
            variant_data = json.loads(variant_data)

        # Backward compat: if stored as list (old format), wrap in dict
        if isinstance(variant_data, list):
            variants = {"variant": variant_data}
        else:
            variants = variant_data
```

And in the `cls(...)` constructor call, replace `variant_modules=variant_modules` with:

```python
            variants=variants,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_experiment/test_experiment_models.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Lint check**

Run: `uv run ruff check perpetual_predict/experiment/models.py tests/test_experiment/`

- [ ] **Step 6: Commit**

```bash
git add perpetual_predict/experiment/models.py tests/test_experiment/
git commit -m "feat: extend Experiment model to support multi-variant dict"
```

---

### Task 2: ExperimentResult model — support per-variant results

**Files:**
- Modify: `perpetual_predict/experiment/models.py`
- Modify: `tests/test_experiment/test_experiment_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_experiment/test_experiment_models.py`:

```python
from perpetual_predict.experiment.models import VariantResult, ExperimentResult


class TestVariantResult:
    def test_create(self):
        vr = VariantResult(
            variant_name="macro",
            sample_size=30,
            accuracy=0.58,
            net_return=2.1,
            sharpe=0.45,
            p_value=0.04,
            is_significant=True,
        )
        assert vr.variant_name == "macro"
        assert vr.is_significant is True


class TestMultiVariantExperimentResult:
    def test_create_with_variant_results(self):
        result = ExperimentResult(
            experiment_id="exp_test",
            control_accuracy=0.52,
            control_return=-1.3,
            control_sharpe=0.12,
            control_sample_size=30,
            variant_results=[
                VariantResult("macro", 30, 0.55, 2.1, 0.45, 0.12, False),
                VariantResult("news", 30, 0.59, 4.2, 0.67, 0.04, True),
            ],
        )
        assert len(result.variant_results) == 2
        assert result.variant_results[1].is_significant is True

    def test_best_variant(self):
        result = ExperimentResult(
            experiment_id="exp_test",
            control_accuracy=0.52,
            control_return=-1.3,
            control_sharpe=0.12,
            control_sample_size=30,
            variant_results=[
                VariantResult("macro", 30, 0.55, 2.1, 0.45, 0.12, False),
                VariantResult("news", 30, 0.59, 4.2, 0.67, 0.04, True),
            ],
        )
        best = result.best_variant(metric="net_return")
        assert best is not None
        assert best.variant_name == "news"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_experiment/test_experiment_models.py::TestVariantResult -v`
Expected: ImportError — cannot import `VariantResult`

- [ ] **Step 3: Implement VariantResult and update ExperimentResult**

In `perpetual_predict/experiment/models.py`, replace the existing `ExperimentResult` dataclass (lines 115-129) with:

```python
@dataclass
class VariantResult:
    """Statistical result for a single variant arm."""

    variant_name: str
    sample_size: int
    accuracy: float
    net_return: float
    sharpe: float
    p_value: float | None = None
    is_significant: bool = False


@dataclass
class ExperimentResult:
    """Statistical analysis result for an experiment (multi-variant)."""

    experiment_id: str
    control_accuracy: float
    control_return: float
    control_sharpe: float
    control_sample_size: int
    variant_results: list[VariantResult] = field(default_factory=list)

    # Backward compat properties
    @property
    def sample_size(self) -> int:
        return self.control_sample_size

    @property
    def variant_accuracy(self) -> float:
        return self.variant_results[0].accuracy if self.variant_results else 0.0

    @property
    def variant_return(self) -> float:
        return self.variant_results[0].net_return if self.variant_results else 0.0

    @property
    def variant_sharpe(self) -> float:
        return self.variant_results[0].sharpe if self.variant_results else 0.0

    @property
    def p_value(self) -> float | None:
        return self.variant_results[0].p_value if self.variant_results else None

    @property
    def is_significant(self) -> bool:
        return self.variant_results[0].is_significant if self.variant_results else False

    @property
    def recommended_winner(self) -> str | None:
        """Backward compat: return best significant variant or None."""
        significant = [v for v in self.variant_results if v.is_significant]
        if not significant:
            return None
        return f"variant_{significant[0].variant_name}"

    def best_variant(self, metric: str = "net_return") -> VariantResult | None:
        """Return the best performing significant variant."""
        significant = [v for v in self.variant_results if v.is_significant]
        if not significant:
            return None
        if metric == "accuracy":
            return max(significant, key=lambda v: v.accuracy)
        elif metric == "sharpe":
            return max(significant, key=lambda v: v.sharpe)
        else:  # net_return
            return max(significant, key=lambda v: v.net_return)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_experiment/test_experiment_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check perpetual_predict/experiment/models.py tests/test_experiment/
git add perpetual_predict/experiment/models.py tests/test_experiment/
git commit -m "feat: add VariantResult and update ExperimentResult for multi-variant"
```

---

### Task 3: Analyzer — multi-variant analysis loop

**Files:**
- Modify: `perpetual_predict/experiment/analyzer.py`
- Create: `tests/test_experiment/test_analyzer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_experiment/test_analyzer.py`:

```python
"""Tests for multi-variant experiment analyzer."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

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
    async def test_analyze_backward_compat_single_variant(self):
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
        # Backward compat properties
        assert result.variant_accuracy > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_experiment/test_analyzer.py -v`
Expected: Failure — analyzer.analyze() doesn't return multi-variant results

- [ ] **Step 3: Rewrite analyzer for multi-variant**

Replace the entire `analyze()` method in `perpetual_predict/experiment/analyzer.py`:

```python
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
```

Keep the existing `_sharpe_ratio`, `_proportions_z_test`, `_welch_t_test`, `_norm_cdf` helper functions unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_experiment/test_analyzer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run pytest tests/ -v`
Expected: All pass (some existing tests may need arm name updates if they reference "variant" directly)

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check perpetual_predict/experiment/analyzer.py tests/test_experiment/
git add perpetual_predict/experiment/analyzer.py tests/test_experiment/
git commit -m "feat: rewrite analyzer for multi-variant experiment analysis"
```

---

### Task 4: Parallel prediction execution in jobs.py

**Files:**
- Modify: `perpetual_predict/scheduler/jobs.py`

- [ ] **Step 1: Refactor prediction_job() for multi-variant parallel execution**

In `perpetual_predict/scheduler/jobs.py`, replace the experiment arm prediction section (lines 531-622) with:

```python
        # 2. Experiment arm predictions (parallel, max 4 concurrent)
        variant_results: list[tuple] = []

        if settings.experiment.enabled:
            async with get_database() as db:
                active_experiments = await db.get_active_experiments()

            # Build prediction tasks for all variants across all experiments
            variant_tasks = []

            for exp in active_experiments:
                # Reuse baseline as control arm
                if prediction:
                    try:
                        async with get_database() as db:
                            control_pred = Prediction(
                                prediction_id=str(uuid.uuid4()),
                                prediction_time=prediction.prediction_time,
                                target_candle_open=target_open,
                                target_candle_close=target_close,
                                symbol=symbol,
                                timeframe=timeframe,
                                direction=prediction.direction,
                                confidence=prediction.confidence,
                                reasoning=prediction.reasoning,
                                key_factors=prediction.key_factors,
                                session_id=prediction.session_id,
                                duration_ms=prediction.duration_ms,
                                model_usage=prediction.model_usage,
                                position_pct=prediction.position_pct,
                                trading_reasoning=prediction.trading_reasoning,
                            )
                            await db.insert_prediction(
                                control_pred,
                                experiment_id=exp.experiment_id,
                                arm="control",
                            )

                            # Open paper trade for control arm
                            if (
                                paper_settings.enabled
                                and control_pred.direction != "NEUTRAL"
                                and control_pred.position_pct > 0
                            ):
                                from perpetual_predict.trading.engine import PaperTradingEngine
                                ctrl_account_id = f"{exp.experiment_id}_control"
                                engine = PaperTradingEngine(db, ctrl_account_id)
                                await engine.ensure_account(paper_settings.initial_balance)
                                candles = await db.get_candles(
                                    symbol=symbol, timeframe=timeframe,
                                    start_time=target_open, end_time=target_open, limit=1,
                                )
                                if candles:
                                    trade = await engine.open_position(control_pred, candles[0].open)
                                    if trade:
                                        logger.info(
                                            f"[control] Paper trade opened (reused baseline): "
                                            f"{trade.side} notional=${trade.notional_value:.2f}"
                                        )
                        logger.info(
                            f"[control] Reused baseline prediction for {exp.experiment_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Experiment {exp.experiment_id} control "
                            f"(baseline reuse) failed (non-fatal): {e}"
                        )

                # Queue variant prediction tasks
                for variant_name, modules in exp.variants.items():
                    variant_tasks.append((
                        exp,
                        variant_name,
                        _run_single_prediction(
                            market_context=market_context,
                            target_open=target_open,
                            target_close=target_close,
                            symbol=symbol,
                            timeframe=timeframe,
                            enabled_modules=modules,
                            experiment_id=exp.experiment_id,
                            arm=f"variant_{variant_name}",
                            account_id=f"{exp.experiment_id}_variant_{variant_name}",
                        ),
                    ))

            # Execute variant predictions in parallel (max 4 at a time)
            MAX_CONCURRENT = 4
            for batch_start in range(0, len(variant_tasks), MAX_CONCURRENT):
                batch = variant_tasks[batch_start:batch_start + MAX_CONCURRENT]
                batch_coros = [task[2] for task in batch]
                batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)

                for i, result in enumerate(batch_results):
                    exp, variant_name, _ = batch[i]
                    if isinstance(result, Exception):
                        logger.warning(
                            f"Experiment {exp.experiment_id} variant_{variant_name} "
                            f"prediction failed (non-fatal): {result}"
                        )
                    elif result:
                        variant_results.append((exp, result))
```

Also remove the `import json` line inside the old loop (line 539) since it's no longer needed there.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All pass

- [ ] **Step 3: Lint + commit**

```bash
uv run ruff check perpetual_predict/scheduler/jobs.py
git add perpetual_predict/scheduler/jobs.py
git commit -m "feat: parallel variant prediction execution with max 4 concurrent"
```

---

### Task 5: CLI experiment create — --variant flag

**Files:**
- Modify: `perpetual_predict/cli/experiment.py`

- [ ] **Step 1: Update CLI parser**

In `perpetual_predict/cli/experiment.py`, update the `create` subparser (lines 30-42):

Replace the `--add` argument with `--variant`:

```python
    create_p.add_argument(
        "--variant", action="append", default=[],
        help=(
            "Variant arm definition. Each --variant creates one arm. "
            "Use comma for module combinations. "
            "Example: --variant macro --variant news --variant macro,news"
        ),
    )
```

Keep `--add` for backward compat but mark as deprecated:

```python
    create_p.add_argument(
        "--add", nargs="*", default=[],
        help="[DEPRECATED: use --variant] Modules to add to a single variant",
    )
```

Remove `--remove` argument (line 37-40) — not needed with new --variant syntax.

Add `--variant` to merge command:

```python
    merge_p.add_argument("--variant", default=None, help="Specific variant to merge")
```

- [ ] **Step 2: Update _create() function**

Replace the `_create()` function (lines 95-158):

```python
async def _create(args) -> int:
    settings = get_settings()
    control_modules = list(DEFAULT_MODULES)

    # Build variants dict
    variants: dict[str, list[str]] = {}

    if args.variant:
        # New --variant syntax
        for variant_spec in args.variant:
            modules_to_add = [m.strip() for m in variant_spec.split(",") if m.strip()]
            for mod in modules_to_add:
                if mod not in SEED_MODULES:
                    print(f"Unknown module: {mod}")
                    print(f"Available: {', '.join(SEED_MODULES)}")
                    return 1
            variant_name = "_".join(modules_to_add)
            variant_modules = list(DEFAULT_MODULES) + [
                m for m in modules_to_add if m not in DEFAULT_MODULES
            ]
            variants[variant_name] = variant_modules
    elif args.add:
        # Backward compat: --add creates single variant
        variant_modules = list(DEFAULT_MODULES)
        for mod in args.add:
            if mod not in SEED_MODULES:
                print(f"Unknown module: {mod}")
                print(f"Available: {', '.join(SEED_MODULES)}")
                return 1
            if mod not in variant_modules:
                variant_modules.append(mod)
        variant_name = "_".join(args.add)
        variants[variant_name] = variant_modules
        print("Note: --add is deprecated, use --variant instead.")

    if not variants:
        print("Error: No variants defined. Use --variant <modules>.")
        return 1

    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=args.name,
        description=args.description,
        status="active",
        control_modules=control_modules,
        variants=variants,
        min_samples=args.min_samples or settings.experiment.default_min_samples,
        significance_level=settings.experiment.default_significance_level,
        primary_metric=args.metric or settings.experiment.default_primary_metric,
        created_at=datetime.now(timezone.utc),
    )

    async with get_database() as db:
        await db.insert_experiment(experiment)
        balance = settings.paper_trading.initial_balance
        await db.insert_experiment_account(experiment.experiment_id, "control", balance)
        for variant_name in variants:
            await db.insert_experiment_account(
                experiment.experiment_id, f"variant_{variant_name}", balance,
            )

    print(f"Experiment created: {experiment.experiment_id}")
    print(f"  Name: {experiment.name}")
    print(f"  Control: {len(control_modules)} modules (baseline)")
    print(f"  Variants ({len(variants)}):")
    for vname, vmods in variants.items():
        added = set(vmods) - set(control_modules)
        print(f"    {vname}: +{', '.join(added)}")
    print(f"  Min samples: {experiment.min_samples}")
    print(f"  Metric: {experiment.primary_metric}")

    if not settings.experiment.enabled:
        print("\n  ⚠️  EXPERIMENT_ENABLED=false — experiments won't run in cycle.")

    return 0
```

- [ ] **Step 3: Update _status() for multi-variant display**

Replace `_status()` function (lines 179-230):

```python
async def _status(args) -> int:
    from perpetual_predict.experiment.analyzer import ExperimentAnalyzer

    async with get_database() as db:
        experiment = await db.get_experiment(args.experiment_id)
        if not experiment:
            print(f"Experiment not found: {args.experiment_id}")
            return 1

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze(args.experiment_id)

    print(f"Experiment: {experiment.name} ({experiment.experiment_id})")
    print(f"Status: {experiment.status}")
    print(f"Metric: {experiment.primary_metric} | Min samples: {experiment.min_samples}")
    print()

    if result:
        # Control row
        print(f"  {'control (baseline)':<25} accuracy {result.control_accuracy:>6.1%}, "
              f"net_return {result.control_return:>+7.2f}%, "
              f"sharpe {result.control_sharpe:>5.2f}")

        # Variant rows
        for vr in result.variant_results:
            sig_mark = " ✓" if vr.is_significant else ""
            p_str = f"(p={vr.p_value:.2f})" if vr.p_value is not None else f"({vr.sample_size} samples)"
            print(f"  variant_{vr.variant_name:<20} accuracy {vr.accuracy:>6.1%}, "
                  f"net_return {vr.net_return:>+7.2f}%, "
                  f"sharpe {vr.sharpe:>5.2f}  {p_str}{sig_mark}")

        print()
        significant = [v for v in result.variant_results if v.is_significant]
        if significant:
            best = result.best_variant(metric=experiment.primary_metric)
            if best:
                print(f"Best variant: {best.variant_name}")
        else:
            min_samples_needed = experiment.min_samples - result.control_sample_size
            if min_samples_needed > 0:
                print(f"Need {min_samples_needed} more samples for statistical test.")
            else:
                print("No statistically significant variant yet.")

    return 0
```

- [ ] **Step 4: Update _merge() for multi-variant**

Replace `_merge()` function (lines 246-282):

```python
async def _merge(args) -> int:
    from perpetual_predict.experiment.analyzer import ExperimentAnalyzer

    async with get_database() as db:
        experiment = await db.get_experiment(args.experiment_id)
        if not experiment:
            print(f"Experiment not found: {args.experiment_id}")
            return 1

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze(args.experiment_id)

        if not result:
            print("No analysis results available.")
            return 1

        # Determine which variant to merge
        target_variant = None
        if hasattr(args, "variant") and args.variant:
            # User specified a variant
            target_variant = next(
                (v for v in result.variant_results if v.variant_name == args.variant),
                None,
            )
            if not target_variant:
                print(f"Variant not found: {args.variant}")
                print(f"Available: {', '.join(v.variant_name for v in result.variant_results)}")
                return 1
            if not target_variant.is_significant:
                print(f"Variant '{args.variant}' is not statistically significant (p={target_variant.p_value}).")
                return 1
        else:
            # Auto-select best significant variant
            target_variant = result.best_variant(metric=experiment.primary_metric)
            if not target_variant:
                print("Cannot merge: no variant is statistically significant yet.")
                return 1

        winner_name = target_variant.variant_name
        winner_modules = experiment.variants.get(winner_name, [])
        print(f"Winner: variant_{winner_name}")
        print(f"Modules: {', '.join(winner_modules)}")

        await db.update_experiment_status(
            args.experiment_id, "completed", winner=f"variant_{winner_name}",
        )
        print(f"\nExperiment {args.experiment_id} completed. Winner: variant_{winner_name}")

    return 0
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check perpetual_predict/cli/experiment.py
git add perpetual_predict/cli/experiment.py
git commit -m "feat: update experiment CLI for multi-variant with --variant flag"
```

---

### Task 6: Full integration test

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Lint all changed files**

Run: `uv run ruff check perpetual_predict/experiment/ perpetual_predict/scheduler/jobs.py perpetual_predict/cli/experiment.py`

- [ ] **Step 3: Verify model backward compat**

Run:
```bash
uv run python -c "
import json
from perpetual_predict.experiment.models import Experiment, DEFAULT_MODULES

# Test old format (list) loads correctly
old_data = {'experiment_id': 'old', 'name': 'old', 'control_modules': json.dumps(list(DEFAULT_MODULES)), 'variant_modules': json.dumps([*DEFAULT_MODULES, 'macro'])}
exp = Experiment.from_dict(old_data)
print('Old format loaded:', type(exp.variants), list(exp.variants.keys()))

# Test new format (dict) loads correctly
new_data = {'experiment_id': 'new', 'name': 'new', 'control_modules': json.dumps(list(DEFAULT_MODULES)), 'variant_modules': json.dumps({'macro': [*DEFAULT_MODULES, 'macro'], 'news': [*DEFAULT_MODULES, 'news']})}
exp2 = Experiment.from_dict(new_data)
print('New format loaded:', type(exp2.variants), list(exp2.variants.keys()))
"
```

Expected:
```
Old format loaded: <class 'dict'> ['variant']
New format loaded: <class 'dict'> ['macro', 'news']
```

- [ ] **Step 4: Verify CLI help**

Run: `uv run python -m perpetual_predict experiment create --help`
Expected: `--variant` flag visible in help output

- [ ] **Step 5: Commit if any remaining changes**

```bash
git status
# If clean, done. If changes remain:
git add -A
git commit -m "test: add multi-variant experiment integration verification"
```
