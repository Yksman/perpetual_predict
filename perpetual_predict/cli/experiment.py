"""CLI commands for A/B testing experiment management."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from perpetual_predict.config import get_settings
from perpetual_predict.experiment.models import DEFAULT_MODULES, SEED_MODULES, Experiment
from perpetual_predict.storage.database import get_database
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


def setup_parser(subparsers) -> None:
    """Register experiment subcommands."""
    exp_parser = subparsers.add_parser(
        "experiment",
        help="A/B testing experiment management",
    )
    exp_sub = exp_parser.add_subparsers(
        title="operations",
        dest="operation",
        help="Experiment operations",
    )

    # create
    create_p = exp_sub.add_parser("create", help="Create a new experiment")
    create_p.add_argument("--name", required=True, help="Experiment name")
    create_p.add_argument("--description", default="", help="Description")
    create_p.add_argument(
        "--add", nargs="*", default=[],
        help=f"Modules to ADD to variant (available: {', '.join(SEED_MODULES)})",
    )
    create_p.add_argument(
        "--remove", nargs="*", default=[],
        help="Modules to REMOVE from variant",
    )
    create_p.add_argument("--min-samples", type=int, default=None)
    create_p.add_argument("--metric", default=None, choices=["accuracy", "net_return", "sharpe"])

    # list
    list_p = exp_sub.add_parser("list", help="List experiments")
    list_p.add_argument("--status", default=None, choices=["active", "paused", "completed"])

    # status
    status_p = exp_sub.add_parser("status", help="Show experiment status and results")
    status_p.add_argument("experiment_id", help="Experiment ID")

    # pause / resume
    pause_p = exp_sub.add_parser("pause", help="Pause an experiment")
    pause_p.add_argument("experiment_id")

    resume_p = exp_sub.add_parser("resume", help="Resume a paused experiment")
    resume_p.add_argument("experiment_id")

    # merge
    merge_p = exp_sub.add_parser("merge", help="Merge winning variant")
    merge_p.add_argument("experiment_id")

    exp_parser.set_defaults(func=run_experiment)


def run_experiment(args) -> int:
    """Route to the appropriate experiment operation."""
    if not args.operation:
        print("Usage: perpetual_predict experiment {create|list|status|pause|resume|merge}")
        return 1

    return asyncio.run(_dispatch(args))


async def _dispatch(args) -> int:
    op = args.operation

    if op == "create":
        return await _create(args)
    elif op == "list":
        return await _list(args)
    elif op == "status":
        return await _status(args)
    elif op == "pause":
        return await _change_status(args.experiment_id, "paused")
    elif op == "resume":
        return await _change_status(args.experiment_id, "active")
    elif op == "merge":
        return await _merge(args)
    else:
        print(f"Unknown operation: {op}")
        return 1


async def _create(args) -> int:
    settings = get_settings()

    # Build variant modules
    control_modules = list(DEFAULT_MODULES)
    variant_modules = list(DEFAULT_MODULES)

    for mod in args.add:
        if mod not in SEED_MODULES:
            print(f"Unknown module: {mod}")
            print(f"Available: {', '.join(SEED_MODULES)}")
            return 1
        if mod not in variant_modules:
            variant_modules.append(mod)

    for mod in args.remove:
        if mod in variant_modules:
            variant_modules.remove(mod)

    if control_modules == variant_modules:
        print("Error: Control and variant have identical modules. Use --add or --remove.")
        return 1

    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=args.name,
        description=args.description,
        status="active",
        control_modules=control_modules,
        variant_modules=variant_modules,
        min_samples=args.min_samples or settings.experiment.default_min_samples,
        significance_level=settings.experiment.default_significance_level,
        primary_metric=args.metric or settings.experiment.default_primary_metric,
        created_at=datetime.now(timezone.utc),
    )

    async with get_database() as db:
        await db.insert_experiment(experiment)
        # Create independent paper accounts for each arm
        balance = settings.paper_trading.initial_balance
        await db.insert_experiment_account(experiment.experiment_id, "control", balance)
        await db.insert_experiment_account(experiment.experiment_id, "variant", balance)

    print(f"Experiment created: {experiment.experiment_id}")
    print(f"  Name: {experiment.name}")
    print(f"  Control: {len(control_modules)} modules")
    print(f"  Variant: {len(variant_modules)} modules")

    # Show diff
    added = set(variant_modules) - set(control_modules)
    removed = set(control_modules) - set(variant_modules)
    if added:
        print(f"  Variant adds: {', '.join(added)}")
    if removed:
        print(f"  Variant removes: {', '.join(removed)}")

    print(f"  Min samples: {experiment.min_samples}")
    print(f"  Metric: {experiment.primary_metric}")

    if not settings.experiment.enabled:
        print("\n  ⚠️  EXPERIMENT_ENABLED=false — experiments won't run in cycle.")
        print("     Set EXPERIMENT_ENABLED=true to activate.")

    return 0


async def _list(args) -> int:
    async with get_database() as db:
        experiments = await db.get_experiments(status=args.status)

    if not experiments:
        print("No experiments found.")
        return 0

    print(f"{'ID':<20} {'Name':<25} {'Status':<12} {'Winner':<10} {'Created'}")
    print("-" * 85)
    for exp in experiments:
        created = exp.created_at.strftime("%Y-%m-%d") if exp.created_at else "—"
        winner = exp.winner or "—"
        print(f"{exp.experiment_id:<20} {exp.name:<25} {exp.status:<12} {winner:<10} {created}")

    return 0


async def _status(args) -> int:
    from perpetual_predict.experiment.analyzer import ExperimentAnalyzer

    async with get_database() as db:
        experiment = await db.get_experiment(args.experiment_id)
        if not experiment:
            print(f"Experiment not found: {args.experiment_id}")
            return 1

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze(args.experiment_id)

        # Account balances
        ctrl_acc = await db.get_experiment_account(args.experiment_id, "control")
        var_acc = await db.get_experiment_account(args.experiment_id, "variant")

    print(f"Experiment: {experiment.name} ({experiment.experiment_id})")
    print(f"Status: {experiment.status}")
    print(f"Metric: {experiment.primary_metric} | Min samples: {experiment.min_samples}")
    print()

    # Module diff
    added = set(experiment.variant_modules) - set(experiment.control_modules)
    removed = set(experiment.control_modules) - set(experiment.variant_modules)
    if added:
        print(f"Variant adds: {', '.join(added)}")
    if removed:
        print(f"Variant removes: {', '.join(removed)}")
    print()

    if result:
        print(f"{'Metric':<20} {'Control':>12} {'Variant':>12}")
        print("-" * 46)
        print(f"{'Samples':<20} {result.sample_size:>12} {result.sample_size:>12}")
        print(f"{'Accuracy':<20} {result.control_accuracy:>11.1%} {result.variant_accuracy:>11.1%}")
        print(f"{'Total Return':<20} {result.control_return:>+11.2f}% {result.variant_return:>+11.2f}%")
        print(f"{'Sharpe Ratio':<20} {result.control_sharpe:>12.2f} {result.variant_sharpe:>12.2f}")

        if ctrl_acc and var_acc:
            print(f"{'Balance':<20} ${ctrl_acc.current_balance:>10.2f} ${var_acc.current_balance:>10.2f}")

        print()
        if result.p_value is not None:
            sig = "✅ YES" if result.is_significant else "❌ No"
            print(f"p-value: {result.p_value:.4f} | Significant: {sig}")
            if result.recommended_winner:
                print(f"Recommended winner: {result.recommended_winner}")
        else:
            remaining = experiment.min_samples - result.sample_size
            print(f"Need {remaining} more samples for statistical test.")

    return 0


async def _change_status(experiment_id: str, new_status: str) -> int:
    async with get_database() as db:
        experiment = await db.get_experiment(experiment_id)
        if not experiment:
            print(f"Experiment not found: {experiment_id}")
            return 1

        await db.update_experiment_status(experiment_id, new_status)
        print(f"Experiment {experiment_id}: {experiment.status} → {new_status}")

    return 0


async def _merge(args) -> int:
    from perpetual_predict.experiment.analyzer import ExperimentAnalyzer

    async with get_database() as db:
        experiment = await db.get_experiment(args.experiment_id)
        if not experiment:
            print(f"Experiment not found: {args.experiment_id}")
            return 1

        analyzer = ExperimentAnalyzer(db)
        result = await analyzer.analyze(args.experiment_id)

        if not result or not result.is_significant:
            print("Cannot merge: results are not statistically significant yet.")
            if result:
                remaining = experiment.min_samples - result.sample_size
                if remaining > 0:
                    print(f"Need {remaining} more samples.")
                elif result.p_value is not None:
                    print(f"p-value ({result.p_value:.4f}) >= significance level ({experiment.significance_level})")
            return 1

        winner = result.recommended_winner
        print(f"Winner: {winner}")

        if winner == "variant":
            print("Variant modules will become the new baseline.")
            print(f"Modules: {', '.join(experiment.variant_modules)}")
        else:
            print("Control wins. No module changes needed.")

        await db.update_experiment_status(
            args.experiment_id, "completed", winner=winner,
        )
        print(f"\nExperiment {args.experiment_id} completed. Winner: {winner}")

    return 0
