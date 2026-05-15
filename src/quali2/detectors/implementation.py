"""Implementation smell detectors.

Detects: Complex Conditional, Complex Method, Empty Catch Clause,
Long Identifier, Long Method, Long Parameter List, Long Statement,
Magic Number, Missing Default, Long Lambda Function, Long Message Chain.
"""

from __future__ import annotations

try:
    from antlr4 import CommonTokenStream, InputStream
    from quali2.antlr.Python3Lexer import Python3Lexer
except ImportError:
    CommonTokenStream = object
    InputStream = object
    Python3Lexer = None

from quali2.domain.models import AnalysisData, Smell, SmellType

LONG_METHOD_LINES = 40
LONG_PARAM_LIST = 7
COMPLEX_METHOD_CC = 15
COMPLEX_CONDITIONAL_BOOLEAN_OPS = 4
LONG_IDENTIFIER_CHARS = 40
LONG_STATEMENT_CHARS = 120
LONG_LAMBDA_LINES = 5
LONG_MESSAGE_CHAIN_DOTS = 4

# ---------------------------------------------------------------------------
# Magic number whitelist — numbers that are universally understood
# ---------------------------------------------------------------------------

WHITELISTED_NUMBERS: set[str] = {
    "0",
    "1",
    "-1",
    "2",
    "10",
    "100",
    "1000",
    "1024",
    "512",
    "2048",
    "4096",
    "8192",
    # Common HTTP codes
    "200",
    "201",
    "400",
    "401",
    "403",
    "404",
    "500",
    # Common bit sizes/masks
    "8",
    "16",
    "32",
    "64",
    "128",
    "256",
    "0xff",
    "0xFF",
}


class TokenScanner:
    """Helper to scan token streams and avoid Data Clumps."""

    def __init__(self, fp: str, tokens: list):
        self.fp = fp
        self.tokens = tokens
        self.n = len(tokens)


def detect_implementation_smells(
    data: AnalysisData,
    source: str,
    token_stream: CommonTokenStream | None = None,
) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path
    lines = source.splitlines()

    if token_stream is None:
        if Python3Lexer is None:
            return []
        input_stream = InputStream(source)
        lexer = Python3Lexer(input_stream)
        token_stream = CommonTokenStream(lexer)
    token_stream.fill()
    tokens = token_stream.tokens

    scanner = TokenScanner(fp, tokens)

    all_funcs = list(data.top_level_functions)
    for cls in data.classes:
        all_funcs.extend(cls.methods)

    smells.extend(_check_function_smells(fp, all_funcs))
    smells.extend(_check_token_smells(scanner))
    smells.extend(_check_line_smells(fp, lines))
    return smells


def _check_function_smells(fp: str, functions: list) -> list[Smell]:
    smells: list[Smell] = []
    for fn in functions:
        smells.extend(_check_single_function(fp, fn))
    return smells


def _check_single_function(fp: str, fn) -> list[Smell]:
    smells = []
    smells.extend(_check_method_length(fp, fn))
    smells.extend(_check_method_complexity(fp, fn))
    smells.extend(_check_parameter_list(fp, fn))
    smells.extend(_check_identifier_length(fp, fn))
    return smells


def _check_method_length(fp: str, fn) -> list[Smell]:
    if fn.num_statements > LONG_METHOD_LINES:
        return [
            Smell.create(
                SmellType.LONG_METHOD,
                fp,
                fn.line_start,
                fn.name,
                f"Method has {fn.num_statements} lines (threshold {LONG_METHOD_LINES})",
            )
        ]
    return []


def _check_method_complexity(fp: str, fn) -> list[Smell]:
    if fn.cyclomatic_complexity > COMPLEX_METHOD_CC:
        elem = f"{fn.name}"
        return [
            Smell.create(
                SmellType.COMPLEX_METHOD,
                fp,
                fn.line_start,
                elem,
                f"Cyclomatic complexity is {fn.cyclomatic_complexity} (threshold {COMPLEX_METHOD_CC})",
            )
        ]
    return []


def _check_parameter_list(fp: str, fn) -> list[Smell]:
    # Filter out self/cls
    params = [p for p in fn.params if p.name not in ("self", "cls")]
    if len(params) > LONG_PARAM_LIST:
        return [
            Smell.create(
                SmellType.LONG_PARAMETER_LIST,
                fp,
                fn.line_start,
                fn.name,
                f"Function has {len(params)} parameters (threshold {LONG_PARAM_LIST})",
            )
        ]
    return []


def _check_identifier_length(fp: str, fn) -> list[Smell]:
    if len(fn.name) > LONG_IDENTIFIER_CHARS:
        return [
            Smell.create(
                SmellType.LONG_IDENTIFIER,
                fp,
                fn.line_start,
                fn.name,
                f"Identifier '{fn.name}' is too long ({len(fn.name)} chars)",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Token-based checks (ANTLR backend)
# ---------------------------------------------------------------------------


def _check_token_smells(scanner: TokenScanner) -> list[Smell]:
    smells: list[Smell] = []
    for i in range(scanner.n):
        t = scanner.tokens[i]
        if t.type == Python3Lexer.TRY:
            smells.extend(_detect_empty_catch_clauses(scanner, i))
        if t.type == Python3Lexer.IF or t.type == Python3Lexer.WHILE:
            smells.extend(_detect_complex_conditionals(scanner, i))
        if t.type == Python3Lexer.MATCH:
            smells.extend(_detect_missing_default(scanner, i))
        if t.type == Python3Lexer.NAME:
            smells.extend(_detect_long_message_chains(scanner, i))
    return smells


def _detect_empty_catch_clauses(scanner: TokenScanner, start: int) -> list[Smell]:
    tokens = scanner.tokens
    n = scanner.n
    # Look for EXCEPT -> COLON -> NEWLINE -> INDENT -> PASS
    for j in range(start, min(start + 50, n)):
        if tokens[j].type == Python3Lexer.EXCEPT:
            colon_idx = _skip_to_colon(scanner, j)
            if colon_idx != -1 and colon_idx + 2 < n:
                # check if next real token is PASS
                next_t = tokens[colon_idx + 1]
                if next_t.type == Python3Lexer.NEWLINE:
                    next_t = tokens[colon_idx + 2]
                if next_t.type == Python3Lexer.INDENT:
                    next_t = tokens[colon_idx + 3]
                if next_t.type == Python3Lexer.PASS:
                    return [
                        Smell.create(
                            SmellType.EMPTY_CATCH_CLAUSE,
                            scanner.fp,
                            tokens[j].line,
                            "<except>",
                            "Exception handler body is empty (pass)",
                        )
                    ]
    return []


def _skip_to_colon(scanner: TokenScanner, start: int) -> int:
    for i in range(start, min(start + 20, scanner.n)):
        if scanner.tokens[i].type == Python3Lexer.COLON:
            return i
    return -1


def _detect_complex_conditionals(scanner: TokenScanner, start: int) -> list[Smell]:
    colon_idx = _skip_to_colon(scanner, start)
    if colon_idx == -1:
        return []

    count = _count_bool_ops(scanner, start, colon_idx)
    if count >= COMPLEX_CONDITIONAL_BOOLEAN_OPS:
        return [
            Smell.create(
                SmellType.COMPLEX_CONDITIONAL,
                scanner.fp,
                scanner.tokens[start].line,
                "<conditional>",
                f"Conditional has {count} boolean operators — consider simplifying",
            )
        ]
    return []


def _count_bool_ops(scanner: TokenScanner, start: int, end: int) -> int:
    count = 0
    for i in range(start, end):
        if scanner.tokens[i].type in (Python3Lexer.AND, Python3Lexer.OR):
            count += 1
    return count


def _detect_missing_default(scanner: TokenScanner, start: int) -> list[Smell]:
    colon_idx = _skip_to_colon(scanner, start)
    if colon_idx == -1:
        return []

    has_default = _scan_case_blocks(scanner, colon_idx)
    if not has_default:
        return [
            Smell.create(
                SmellType.MISSING_DEFAULT,
                scanner.fp,
                scanner.tokens[start].line,
                "<match>",
                "Match statement has no default 'case _' clause",
            )
        ]
    return []


def _scan_case_blocks(scanner: TokenScanner, start: int) -> bool:
    for i in range(start, min(start + 200, scanner.n)):
        if scanner.tokens[i].type == Python3Lexer.CASE:
            if i + 1 < scanner.n and scanner.tokens[i + 1].text == "_":
                return True
    return False


def _count_dot_chain(scanner: TokenScanner, start: int) -> int:
    count = 0
    curr = start
    while curr + 2 < scanner.n:
        if scanner.tokens[curr + 1].type == Python3Lexer.DOT and scanner.tokens[curr + 2].type == Python3Lexer.NAME:
            count += 1
            curr += 2
        else:
            break
    return count


def _detect_long_message_chains(scanner: TokenScanner, i: int) -> list[Smell]:
    if i > 0 and scanner.tokens[i - 1].type == Python3Lexer.DOT:
        return []

    dots = _count_dot_chain(scanner, i)
    if dots >= LONG_MESSAGE_CHAIN_DOTS:
        return [
            Smell.create(
                SmellType.LONG_MESSAGE_CHAIN,
                scanner.fp,
                scanner.tokens[i].line,
                scanner.tokens[i].text,
                f"Message chain has {dots} dots (threshold {LONG_MESSAGE_CHAIN_DOTS})",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Line-based checks (no regex)
# ---------------------------------------------------------------------------


def _is_fn_line(stripped: str) -> bool:
    """Check if line contains 'lambda' keyword safely."""
    import re
    return bool(re.search(r'\blambda\b', stripped))


def _check_line_smells(fp: str, lines: list[str]) -> list[Smell]:
    smells: list[Smell] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
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
        if _is_fn_line(stripped):
            indent = len(line) - len(line.lstrip())
            span = _count_continuation_lines(lines, i - 1, indent)
            if span > LONG_LAMBDA_LINES:
                smells.append(
                    Smell.create(
                        SmellType.LONG_LAMBDA_FUNCTION,
                        fp,
                        i,
                        "<lambda>",
                        f"Lambda spans {span} lines (threshold {LONG_LAMBDA_LINES})",
                    )
                )
    return smells


def _count_continuation_lines(lines: list[str], start_idx: int, indent: int) -> int:
    count = 1
    for i in range(start_idx + 1, len(lines)):
        if not lines[i].strip():
            continue
        if len(lines[i]) - len(lines[i].lstrip()) > indent:
            count += 1
        else:
            break
    return count
