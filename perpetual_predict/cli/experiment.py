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
        "--variant", action="append", default=[],
        help=(
            "Variant arm definition. Each --variant creates one arm. "
            "Use comma for module combinations. "
            "Example: --variant macro --variant news --variant macro,news"
        ),
    )
    create_p.add_argument(
        "--add", nargs="*", default=[],
        help="[DEPRECATED: use --variant] Modules to add to a single variant",
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
    merge_p.add_argument("--variant", default=None, help="Specific variant to merge")

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
    control_modules = list(DEFAULT_MODULES)

    # Build variants dict
    variants: dict[str, list[str]] = {}

    if args.variant:
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

    print(f"Experiment: {experiment.name} ({experiment.experiment_id})")
    print(f"Status: {experiment.status}")
    print(f"Metric: {experiment.primary_metric} | Min samples: {experiment.min_samples}")
    print()

    if result:
        print(f"  {'control (baseline)':<25} accuracy {result.control_accuracy:>6.1%}, "
              f"net_return {result.control_return:>+7.2f}%, "
              f"sharpe {result.control_sharpe:>5.2f}")

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

        if not result:
            print("No analysis results available.")
            return 1

        target_variant = None
        if hasattr(args, "variant") and args.variant:
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
