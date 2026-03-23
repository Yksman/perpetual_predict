"""CLI command for exporting dashboard data."""

import argparse
import asyncio

from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Setup the export command parser."""
    parser = subparsers.add_parser(
        "export",
        help="Export dashboard data (predictions, trades, metrics) to JSON files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for JSON files (default: from settings)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Days of history to include (default: 90)",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push exported files to git data branch after export",
    )
    parser.set_defaults(func=run_export)


def run_export(args: argparse.Namespace) -> int:
    """Run the export command."""
    try:
        return asyncio.run(_run_export_async(args))
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1


async def _run_export_async(args: argparse.Namespace) -> int:
    """Async implementation of export command."""
    from perpetual_predict.export.exporter import (
        export_dashboard_data,
        push_to_data_branch,
    )

    output_path = await export_dashboard_data(
        output_dir=args.output_dir,
        history_days=args.days,
    )
    print(f"Exported dashboard data to {output_path}")

    if args.push:
        success = push_to_data_branch(output_path)
        if success:
            print("Pushed to data branch successfully")
        else:
            print("Failed to push to data branch")
            return 1

    return 0
