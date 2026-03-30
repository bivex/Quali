"""Implementation smell detectors.

Detects: Complex Conditional, Complex Method, Empty Catch Clause,
Long Identifier, Long Method, Long Parameter List, Long Statement,
Magic Number, Missing Default, Long Lambda Function, Long Message Chain.
"""

from __future__ import annotations

import re

from antlr4 import CommonTokenStream, InputStream

from quali2.antlr.Python3Lexer import Python3Lexer
from quali2.domain.models import AnalysisData, Smell, SmellType

LONG_METHOD_LINES = 40
LONG_PARAM_LIST = 7
COMPLEX_METHOD_CC = 15
COMPLEX_CONDITIONAL_BOOLEAN_OPS = 4
LONG_IDENTIFIER_CHARS = 40
LONG_STATEMENT_CHARS = 120
LONG_LAMBDA_LINES = 5
LONG_MESSAGE_CHAIN_DOTS = 4
EXCEPT_PATTERN = re.compile(
    r"except\s+[\w.]+(?:\s+as\s+\w+)?\s*:\s*(?:pass|\.\.\.)\s*$",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Magic number whitelist — numbers that are universally understood
# ---------------------------------------------------------------------------

WHITELISTED_NUMBERS: set[str] = {
    # Single digits
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    # Powers of two / common sizes
    "16",
    "32",
    "64",
    "128",
    "256",
    "512",
    "1024",
    "2048",
    "4096",
    "8192",
    # Percentages / ratios
    "10",
    "100",
    "1000",
    "10000",
    # HTTP success
    "200",
    "201",
    "202",
    "204",
    # HTTP redirect
    "301",
    "302",
    "304",
    "307",
    "308",
    # HTTP client error
    "400",
    "401",
    "403",
    "404",
    "405",
    "408",
    "409",
    "422",
    "429",
    # HTTP server error
    "500",
    "501",
    "502",
    "503",
    "504",
    # Time
    "60",
    "3600",
    "24",
    "7",
    "12",
    "30",
    "31",
    "365",
    # Common
    "0.0",
    "1.0",
    "-1",
    "-1.0",
    # Char codes
    "255",
    "127",
    # Hex equivalents
    "0xff",
    "0xFF",
    "0x0",
    "0x00",
    # Octal equivalents
    "0o755",
    "0o644",
    "0o0",
}

# Matches a numeric literal (int, float, hex, oct, bin, complex)
NUMBER_PATTERN = re.compile(
    r"""
    (?<![.\w])              # not preceded by dot or word-char
    (
        0[xXoObB][\da-fA-F_]+  # hex/oct/bin
      | \d[\d_]*               # integer
        (?:\.\d[\d_]*?)?       # optional fractional part
        (?:[eE][+-]?\d+)?      # optional exponent
      | \.\d[\d_]*             # starts with dot
        (?:[eE][+-]?\d+)?      # optional exponent
      | \d[\d_]*[jJ]           # imaginary
    )
    (?![.\w])               # not followed by dot or word-char
    """,
    re.VERBOSE,
)

# Pattern that matches a constant assignment line:  UPPER_CASE = number
CONSTANT_ASSIGN_RE = re.compile(
    r"^[ \t]*[A-Z][A-Z0-9_]*[ \t]*=[ \t]*\S",
    re.MULTILINE,
)


def detect_implementation_smells(
    data: AnalysisData,
    source: str,
    token_stream: CommonTokenStream | None = None,
) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path
    lines = source.splitlines()

    # Scan all functions (top-level + methods)
    all_funcs = list(data.top_level_functions)
    for cls in data.classes:
        all_funcs.extend(cls.methods)

    for fn in all_funcs:
        elem = fn.name

        # Long Method
        method_lines = fn.line_end - fn.line_start + 1
        if method_lines > LONG_METHOD_LINES:
            smells.append(
                Smell.create(
                    SmellType.LONG_METHOD,
                    fp,
                    fn.line_start,
                    elem,
                    f"Method spans {method_lines} lines (threshold {LONG_METHOD_LINES})",
                )
            )

        # Long Parameter List
        if len(fn.params) > LONG_PARAM_LIST:
            smells.append(
                Smell.create(
                    SmellType.LONG_PARAMETER_LIST,
                    fp,
                    fn.line_start,
                    elem,
                    f"Method has {len(fn.params)} parameters (threshold {LONG_PARAM_LIST})",
                )
            )

        # Complex Method
        if fn.cyclomatic_complexity > COMPLEX_METHOD_CC:
            smells.append(
                Smell.create(
                    SmellType.COMPLEX_METHOD,
                    fp,
                    fn.line_start,
                    elem,
                    f"Cyclomatic complexity is {fn.cyclomatic_complexity} (threshold {COMPLEX_METHOD_CC})",
                )
            )

        # Long Identifier
        if len(fn.name) > LONG_IDENTIFIER_CHARS:
            smells.append(
                Smell.create(
                    SmellType.LONG_IDENTIFIER,
                    fp,
                    fn.line_start,
                    elem,
                    f"Identifier '{fn.name}' is {len(fn.name)} chars (threshold {LONG_IDENTIFIER_CHARS})",
                )
            )

    # Empty Catch Clause (from source regex)
    for match in EXCEPT_PATTERN.finditer(source):
        line_num = source[: match.start()].count("\n") + 1
        smells.append(
            Smell.create(
                SmellType.EMPTY_CATCH_CLAUSE,
                fp,
                line_num,
                "<except>",
                "Exception handler body is empty (pass or ...)",
            )
        )

    # ── Magic Numbers (ANTLR4 token-stream based) ──────────────────────
    smells.extend(_detect_magic_numbers(fp, source, token_stream))

    # ── Line-level checks ──────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Long Statement
        if len(stripped) > LONG_STATEMENT_CHARS and not stripped.startswith("#"):
            smells.append(
                Smell.create(
                    SmellType.LONG_STATEMENT,
                    fp,
                    i,
                    "<line>",
                    f"Line has {len(stripped)} characters (threshold {LONG_STATEMENT_CHARS})",
                )
            )

        # Long Lambda
        if "lambda" in stripped:
            indent = len(line) - len(line.lstrip())
            lambda_lines = _count_lambda_lines(lines, i - 1, indent)
            if lambda_lines > LONG_LAMBDA_LINES:
                smells.append(
                    Smell.create(
                        SmellType.LONG_LAMBDA_FUNCTION,
                        fp,
                        i,
                        "<lambda>",
                        f"Lambda spans {lambda_lines} lines (threshold {LONG_LAMBDA_LINES})",
                    )
                )

        # Long Message Chain
        chain_match = re.search(
            r"(\w+(?:\.\w+){%d,})" % LONG_MESSAGE_CHAIN_DOTS, stripped
        )
        if chain_match and not stripped.strip().startswith("#"):
            dots = chain_match.group(1).count(".")
            if dots >= LONG_MESSAGE_CHAIN_DOTS:
                smells.append(
                    Smell.create(
                        SmellType.LONG_MESSAGE_CHAIN,
                        fp,
                        i,
                        "<line>",
                        f"Message chain has {dots} dot accesses (threshold {LONG_MESSAGE_CHAIN_DOTS})",
                    )
                )

    # Complex Conditional — boolean-heavy if/elif
    bool_op_pattern = re.compile(
        r"\b(if|elif)\b\s+.*?(?:and|or).*?(?:and|or).*?(?:and|or)"
    )
    for match in bool_op_pattern.finditer(source):
        line_num = source[: match.start()].count("\n") + 1
        smells.append(
            Smell.create(
                SmellType.COMPLEX_CONDITIONAL,
                fp,
                line_num,
                "<conditional>",
                "Conditional has 4+ boolean operators — consider simplifying",
            )
        )

    # Missing Default — match without wildcard case
    match_pattern = re.compile(r"\bmatch\b\s+[\w.]+")
    case_pattern = re.compile(r"\bcase\s+_\b")
    for m in match_pattern.finditer(source):
        line_num = source[: m.start()].count("\n") + 1
        block_start = m.start()
        block_end = _find_block_end(source, block_start)
        block_text = source[block_start:block_end]
        if not case_pattern.search(block_text):
            smells.append(
                Smell.create(
                    SmellType.MISSING_DEFAULT,
                    fp,
                    line_num,
                    "<match>",
                    "Match statement has no default 'case _' clause",
                )
            )

    return smells


# ---------------------------------------------------------------------------
# Magic number detection — ANTLR4 token stream + context-aware filtering
# ---------------------------------------------------------------------------


def _detect_magic_numbers(
    fp: str,
    source: str,
    token_stream: CommonTokenStream | None = None,
) -> list[Smell]:
    """Detect magic numbers using ANTLR4 tokenisation.

    Strategy:
      1. Reuse token_stream if provided, else lex the source.
      2. For each NUMBER token, extract the full line of source.
      3. Skip if the number is in the whitelist.
      4. Skip if the line is a constant assignment (UPPER_CASE = number).
      5. Skip if the number appears inside a string literal or comment.
      6. Otherwise report as a magic number.
    """
    smells: list[Smell] = []

    # Build or reuse token stream
    if token_stream is not None:
        token_stream.fill()
    else:
        input_stream = InputStream(source)
        lexer = Python3Lexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        token_stream.fill()

    lines = source.splitlines()

    # Pre-compute constant assignment lines (lines like  UPPER_CASE = 42)
    const_lines: set[int] = set()
    for m in CONSTANT_ASSIGN_RE.finditer(source):
        const_lines.add(source[: m.start()].count("\n") + 1)

    for token in token_stream.tokens:
        # Skip EOF and non-NUMBER tokens
        if token.type == -1 or token.type != Python3Lexer.NUMBER:
            continue

        line_no = token.line
        num_text = token.text.strip()

        # Skip whitelisted values
        if num_text in WHITELISTED_NUMBERS:
            continue

        # Skip constant assignment lines
        if line_no in const_lines:
            continue

        # Skip if inside a string or comment (check column position)
        if line_no <= len(lines):
            line_text = lines[line_no - 1]
            col = token.column
            if _is_in_string_or_comment(line_text, col, len(num_text)):
                continue

        # Determine the containing element
        element = _find_containing_func(data=None, line_no=line_no, lines=lines)

        smells.append(
            Smell.create(
                SmellType.MAGIC_NUMBER,
                fp,
                line_no,
                element,
                f"Magic number '{num_text}' — consider extracting to a named constant",
            )
        )

    return smells


def _find_containing_func(data, line_no: int, lines: list[str]) -> str:
    """Best-effort: walk backwards from line_no to find the enclosing def/class."""
    for i in range(line_no - 1, -1, -1):
        stripped = lines[i].lstrip()
        m = re.match(r"(?:def|class)\s+(\w+)", stripped)
        if m:
            return m.group(1)
    return "<module>"


def _is_in_string_or_comment(line: str, col: int, num_len: int) -> bool:
    """Check if the number at *col* is inside a string or comment."""
    before = line[:col]
    after = line[col + num_len :]

    # Check for comment
    if "#" in before:
        return True

    # Check for triple-quoted strings (simple heuristic: count quotes before col)
    for quote in ('"""', "'''"):
        if quote in line:
            return True

    # Check for single-quoted strings
    in_single = before.count("'") % 2 != 0
    in_double = before.count('"') % 2 != 0
    if in_single or in_double:
        return True

    # Check if preceded by a dot (e.g. 3.14 — the 14 is part of a float)
    if col > 0 and line[col - 1] == ".":
        return True

    return False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _count_lambda_lines(lines: list[str], start_idx: int, indent: int) -> int:
    count = 1
    for i in range(start_idx + 1, len(lines)):
        if not lines[i].strip():
            continue
        if len(lines[i]) - len(lines[i].lstrip()) > indent:
            count += 1
        else:
            break
    return count


def _find_block_end(source: str, start: int) -> int:
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
        elif source[i] == ":" and depth == 0:
            return min(i + 200, len(source))
    return len(source)
