#!/usr/bin/env bash
set -euo pipefail

# quali2 — Analyze any Python project for code smells
# Usage:
#   ./quali.sh <path>                # text output
#   ./quali.sh <path> -f json        # JSON output
#   ./quali.sh <path> -o report.json # save JSON to file
#   ./quali.sh <path> --summary      # summary only

# Resolve symlink
SELF="${BASH_SOURCE[0]}"
while [[ -L "$SELF" ]]; do SELF="$(readlink "$SELF")"; done
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/src${PYTHONPATH:+:$PYTHONPATH}"

usage() {
    cat <<'EOF'
Usage: quali.sh <path> [options]

Options:
  -f, --format <text|json>   Output format (default: text)
  -b, --backend <ast|antlr>  Parser backend (default: ast)
  -o, --output <file>        Save output to file
  -s, --summary              Show only summary (smells + counts)
  -q, --quiet                Suppress stderr (ANTLR warnings)
  -h, --help                 Show this help

Examples:
  ./quali.sh ~/myproject
  ./quali.sh src/ --summary
  ./quali.sh . -f json -o report.json
  ./quali.sh ~/django-app -s -q
  ./quali.sh . -b antlr       # use ANTLR4 parser (requires antlr4-python3-runtime)
EOF
    exit 0
}

# ── Parse args ─────────────────────────────────────────────────────────────

TARGET=""
FORMAT="text"
BACKEND="ast"
OUTPUT=""
SUMMARY=false
QUIET=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)    usage ;;
        -f|--format)  FORMAT="$2"; shift 2 ;;
        -b|--backend) BACKEND="$2"; shift 2 ;;
        -o|--output)  OUTPUT="$2"; shift 2 ;;
        -s|--summary) SUMMARY=true; shift ;;
        -q|--quiet)   QUIET=true; shift ;;
        -*)           echo "Unknown option: $1" >&2; exit 1 ;;
        *)            TARGET="$1"; shift ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    echo "Error: no path specified" >&2
    echo "Run './quali.sh --help' for usage" >&2
    exit 1
fi

if [[ ! -e "$TARGET" ]]; then
    echo "Error: path '$TARGET' not found" >&2
    exit 1
fi

# ── Find Python ────────────────────────────────────────────────────────────

if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON="${SCRIPT_DIR}/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "Error: Python not found" >&2
    exit 1
fi

# ── Check dependencies ─────────────────────────────────────────────────────

if ! "$PYTHON" -c "import quali2" 2>/dev/null; then
    echo "Error: quali2 not importable" >&2
    echo "  cd ${SCRIPT_DIR} && pip install -e ." >&2
    exit 1
fi

if [[ "$BACKEND" == "antlr" ]] && ! "$PYTHON" -c "import antlr4" 2>/dev/null; then
    echo "Error: antlr4-python3-runtime not installed" >&2
    echo "  pip install 'antlr4-python3-runtime>=4.13'" >&2
    echo "  or use: ./quali.sh ... -b ast" >&2
    exit 1
fi

# ── Build command ──────────────────────────────────────────────────────────

CMD=("$PYTHON" -m quali2 "$TARGET" --backend "$BACKEND")

if [[ "$FORMAT" == "json" ]]; then
    CMD+=(--format json)
fi

STDERR_FLAG="2>/dev/null"
[[ "$QUIET" == false ]] && STDERR_FLAG=""

# ── Run ────────────────────────────────────────────────────────────────────

run_full() {
    if [[ -n "$OUTPUT" ]]; then
        if [[ "$QUIET" == true ]]; then
            "${CMD[@]}" 2>/dev/null > "$OUTPUT"
        else
            "${CMD[@]}" > "$OUTPUT"
        fi
        echo "Report saved to: $OUTPUT" >&2
    else
        if [[ "$QUIET" == true ]]; then
            "${CMD[@]}" 2>/dev/null
        else
            "${CMD[@]}"
        fi
    fi
}

run_summary() {
    local raw
    if [[ "$QUIET" == true ]]; then
        raw=$("${CMD[@]}" 2>/dev/null)
    else
        raw=$("${CMD[@]}" 2>&1)
    fi

    # Print summary block
    echo "$raw" | awk '/^  Summary$/{p=1} p'

    # Print smells if any
    if echo "$raw" | grep -q "^\s*\[!"; then
        echo ""
        echo "Detected smells:"
        echo "$raw" | grep "^\s*\[" | sed 's/^/  /'
    fi
}

if [[ "$SUMMARY" == true ]]; then
    run_summary
else
    run_full
fi
