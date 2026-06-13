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
        "--backend",
        "-b",
        choices=["ast", "antlr"],
        default="ast",
        help="Parser backend: 'ast' (stdlib, default) or 'antlr' (requires antlr4-python3-runtime)",
    )
    parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="Show summary only (text format): skip per-file smell/metric listings",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write report to FILE instead of stdout",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress/status messages on stderr",
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
        report = analyze_project(args.path, backend=args.backend)
    except FileNotFoundError:
        print(f"Error: path '{args.path}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        output = format_json(report)
    else:
        output = format_text(report, summary_only=args.summary)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
        except OSError as exc:
            print(f"Error: cannot write to '{args.output}': {exc}", file=sys.stderr)
            sys.exit(1)
        if not args.quiet:
            print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
