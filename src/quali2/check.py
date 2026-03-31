"""Pre-run quality gate: analyze then execute.

Usage:
    python -m quali2.check script.py [args...]

Analyzes the script with quali2, prints any detected smells, then
executes the script. Non-zero exit only if the script itself fails.
"""

from __future__ import annotations

import subprocess
import sys

from quali2.analysis.engine import analyze_file


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m quali2.check <script.py> [args...]", file=sys.stderr)
        sys.exit(1)

    target = sys.argv[1]
    script_args = sys.argv[2:]

    # ── Analyze ─────────────────────────────────────────────────────────
    try:
        report = analyze_file(target, backend="ast")
    except Exception:
        pass
    else:
        if report.smells:
            print(f"{'─' * 40}")
            print(f"  quali2: {len(report.smells)} smell(s) in {target}")
            print(f"{'─' * 40}")
            for s in report.smells[:10]:
                sev = "!!" if s.severity.value == "High" else "! "
                print(
                    f"  [{sev}] L{s.line:>4}  [{s.category.value}] {s.smell_type.value}"
                )
                print(f"        {s.element}: {s.message}")
            if len(report.smells) > 10:
                print(f"  ... and {len(report.smells) - 10} more")
            print()

    # ── Execute ─────────────────────────────────────────────────────────
    result = subprocess.run([sys.executable, target, *script_args])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
