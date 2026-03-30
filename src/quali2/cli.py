"""CLI entry point for quali2."""

from __future__ import annotations

import argparse
import sys

from quali2.analysis.engine import analyze_project
from quali2.reporting import format_json, format_text


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="quali2",
        description="Quali2 — Python code quality assessment tool",
    )
    parser.add_argument(
        "path",
        help="File or directory to analyze",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version="quali2 0.1.0",
    )

    args = parser.parse_args(argv)

    try:
        report = analyze_project(args.path)
    except FileNotFoundError:
        print(f"Error: path '{args.path}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(format_json(report))
    else:
        print(format_text(report))


if __name__ == "__main__":
    main()
