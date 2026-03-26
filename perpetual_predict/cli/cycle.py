"""CLI command for running the full prediction cycle."""

import argparse
import asyncio
import fcntl
import os
from pathlib import Path

from perpetual_predict.scheduler.health import HealthStatus
from perpetual_predict.scheduler.jobs import (
    collection_job,
    evaluation_job,
    full_cycle_job,
    prediction_job,
)
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)

# Lock file to prevent concurrent execution
LOCK_FILE = Path("/tmp/perpetual_predict_cycle.lock")


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Setup the cycle command parser.

    Args:
        subparsers: Subparser action to add command to.
    """
    parser = subparsers.add_parser(
        "cycle",
        help="Run the full prediction cycle (collect → evaluate → predict)",
    )
    parser.add_argument(
        "--phase",
        choices=["all", "evaluate", "collect", "predict"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.set_defaults(func=run_cycle)


def run_cycle(args: argparse.Namespace) -> int:
    """Run the prediction cycle.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    lock_fd = None
    try:
        # Acquire exclusive lock to prevent concurrent execution
        lock_fd = open(LOCK_FILE, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            logger.debug(f"Acquired lock: {LOCK_FILE}")
        except BlockingIOError:
            logger.error("Another cycle is already running. Exiting.")
            return 1

        return asyncio.run(_run_cycle_async(args))
    except KeyboardInterrupt:
        logger.info("Cycle interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Cycle failed: {e}")
        return 1
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
                LOCK_FILE.unlink(missing_ok=True)
                logger.debug("Released lock")
            except Exception:
                pass


async def _run_cycle_async(args: argparse.Namespace) -> int:
    """Async implementation of cycle command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    health_status = HealthStatus()

    if args.phase == "all":
        logger.info("Running full prediction cycle...")
        results = await full_cycle_job(health_status)

        if results.get("success"):
            _print_cycle_summary(results)
            return 0
        else:
            logger.error(f"Cycle failed: {results.get('error')}")
            return 1

    elif args.phase == "evaluate":
        logger.info("Running evaluation only...")
        results = await evaluation_job(health_status)
        logger.info(f"Evaluated {len(results)} predictions")
        return 0

    elif args.phase == "collect":
        logger.info("Running collection only...")
        results = await collection_job(health_status)
        logger.info(f"Collected: {results}")
        return 0

    elif args.phase == "predict":
        logger.info("Running prediction only...")
        prediction, _variant_results = await prediction_job(health_status)
        if prediction:
            logger.info(
                f"Prediction: {prediction.direction} "
                f"(confidence: {prediction.confidence:.0%})"
            )
            logger.info(f"Reasoning: {prediction.reasoning}")
            return 0
        else:
            logger.error("No prediction generated")
            return 1

    return 0


def _print_cycle_summary(results: dict) -> None:
    """Print a summary of the cycle results.

    Args:
        results: Results dictionary from full_cycle_job.
    """
    print("\n" + "=" * 50)
    print("Prediction Cycle Summary")
    print("=" * 50)

    # Evaluation summary
    eval_results = results.get("evaluation", {})
    if eval_results and not eval_results.get("error"):
        eval_list = eval_results.get("results", [])
        correct = sum(1 for r in eval_list if r.get("is_correct"))
        print(f"\nEvaluation: {correct}/{len(eval_list)} predictions correct")

    # Collection summary
    collection = results.get("collection", {})
    if collection:
        total = sum(collection.values())
        print(f"\nCollection: {total} records collected")

    # Prediction summary
    pred = results.get("prediction", {})
    if pred:
        print("\nNew Prediction:")
        print(f"  Direction: {pred.get('direction')}")
        print(f"  Confidence: {pred.get('confidence', 0) * 100:.0f}%")
        print(f"  Target: {pred.get('target_candle')}")
        print("\n  Key Factors:")
        for factor in pred.get("key_factors", []):
            print(f"    - {factor}")
        print(f"\n  Reasoning: {pred.get('reasoning')}")

    print("\n" + "=" * 50)
