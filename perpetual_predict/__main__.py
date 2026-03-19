"""CLI entry point for perpetual_predict."""

import argparse
import sys

from perpetual_predict.cli import collect, daemon, report


def main() -> int:
    """Main entry point for CLI commands."""
    parser = argparse.ArgumentParser(
        prog="perpetual_predict",
        description="BTCUSDT.P Futures Analysis System",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        help="Available commands",
    )

    # Setup subcommand parsers
    collect.setup_parser(subparsers)
    report.setup_parser(subparsers)
    daemon.setup_parser(subparsers)

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # Run the command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
