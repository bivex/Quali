#!/usr/bin/env bash
# quali2/run.py: pre-run quality gate
# Usage: python -m quali2.run script.py [args...]
# Analyzes the script, prints smells, then executes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Parse arguments ─────────────────────────────────────────────────────────

TARGET="$1"
shift
SCRIPT_ARGS=("$@")

if [[ ! -f "$TARGET" ]]; then
    echo "Error: file '$TARGET' not found" >&2
    exit 1
fi

# ── Run quali2 ──────────────────────────────────────────────────────────────

export PYTHONPATH="${ROOT_DIR}/src"

REPORT=$(python3 -m quali2 "$TARGET" --backend ast 2>/dev/null) || true

# Extract smell summary
SMELLS=$(echo "$REPORT" | grep "Total smells" | awk '{print $NF}')

if [[ -n "$SMELLS" && "$SMELLS" -gt 0 ]]; then
    echo "────────────────────────────────────────"
    echo "  quali2: ${SMELLS} smell(s) in ${TARGET}"
    echo "────────────────────────────────────────"
    echo "$REPORT" | grep "^\s*\[!" | head -10 | sed 's/^/  /'
    echo ""
fi

# ── Run the actual script ───────────────────────────────────────────────────

exec python3 "$TARGET" "${SCRIPT_ARGS[@]}"
