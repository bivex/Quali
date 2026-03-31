"""CLI entry point for quali2."""

from __future__ import annotations

import argparse
import sys

from quali2.analysis.engine import analyze_project
from quali2.reporting import format_json, format_text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quali2",
        description="Quali2 — Python code quality assessment tool",
    )
    parser.add_argument("path", help="File or directory to analyze")
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
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        report = analyze_project(args.path)
    except FileNotFoundError:
        print(f"Error: path '{args.path}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    output = format_json(report) if args.format == "json" else format_text(report)
    print(output)


if __name__ == "__main__":
    main()
