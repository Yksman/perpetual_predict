"""CLI entry point for perpetual_predict."""

import sys


def main() -> int:
    """Main entry point for CLI commands."""
    if len(sys.argv) < 2:
        print("Usage: python -m perpetual_predict <command>")
        print("Commands: collect, report")
        return 1

    command = sys.argv[1]

    if command == "collect":
        print("Data collection not yet implemented")
        return 0
    elif command == "report":
        print("Report generation not yet implemented")
        return 0
    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
