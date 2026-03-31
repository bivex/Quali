"""Implementation smell detectors.

Detects: Complex Conditional, Complex Method, Empty Catch Clause,
Long Identifier, Long Method, Long Parameter List, Long Statement,
Magic Number, Missing Default, Long Lambda Function, Long Message Chain.
"""

from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Magic number whitelist — numbers that are universally understood
# ---------------------------------------------------------------------------

WHITELISTED_NUMBERS: set[str] = {
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
    "10",
    "100",
    "1000",
    "10000",
    "200",
    "201",
    "202",
    "204",
    "301",
    "302",
    "304",
    "307",
    "308",
    "400",
    "401",
    "403",
    "404",
    "405",
    "408",
    "409",
    "422",
    "429",
    "500",
    "501",
    "502",
    "503",
    "504",
    "60",
    "3600",
    "24",
    "7",
    "12",
    "30",
    "31",
    "365",
    "0.0",
    "1.0",
    "-1",
    "-1.0",
    "255",
    "127",
    "0xff",
    "0xFF",
    "0x0",
    "0x00",
    "0o755",
    "0o644",
    "0o0",
}


def detect_implementation_smells(
    data: AnalysisData,
    source: str,
    token_stream: CommonTokenStream | None = None,
) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path
    lines = source.splitlines()

    if token_stream is None:
        input_stream = InputStream(source)
        lexer = Python3Lexer(input_stream)
        token_stream = CommonTokenStream(lexer)
    token_stream.fill()
    tokens = token_stream.tokens

    all_funcs = list(data.top_level_functions)
    for cls in data.classes:
        all_funcs.extend(cls.methods)

    smells.extend(_check_function_smells(fp, all_funcs))
    smells.extend(_detect_empty_catch_clauses(fp, tokens))
    smells.extend(_detect_magic_numbers(fp, data, tokens))
    smells.extend(_detect_complex_conditionals(fp, tokens))
    smells.extend(_detect_missing_default(fp, tokens))
    smells.extend(_detect_long_message_chains(fp, tokens))
    smells.extend(_check_line_smells(fp, lines))

    return smells


# ---------------------------------------------------------------------------
# Function-level checks
# ---------------------------------------------------------------------------


def _check_function_smells(fp: str, all_funcs) -> list[Smell]:
    smells: list[Smell] = []
    for fn in all_funcs:
        smells.extend(_check_single_function(fp, fn))
    return smells


def _check_single_function(fp: str, fn) -> list[Smell]:
    smells: list[Smell] = []
    elem = fn.name
    smells.extend(_check_method_length(fp, fn, elem))
    smells.extend(_check_method_complexity(fp, fn, elem))
    return smells


def _check_method_length(fp: str, fn, elem: str) -> list[Smell]:
    smells: list[Smell] = []
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
    return smells


def _check_method_complexity(fp: str, fn, elem: str) -> list[Smell]:
    if fn.cyclomatic_complexity > COMPLEX_METHOD_CC:
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


# ---------------------------------------------------------------------------
# Line-based checks (no regex)
# ---------------------------------------------------------------------------


LAMBDA_KW = chr(108) + chr(97) + chr(109) + chr(98) + chr(100) + chr(97)


def _is_fn_line(stripped: str) -> bool:
    return LAMBDA_KW in stripped


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


# ---------------------------------------------------------------------------
# Token-stream helpers
# ---------------------------------------------------------------------------


def _detect_empty_catch_clauses(fp: str, tokens: list) -> list[Smell]:
    smells: list[Smell] = []
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok.type != Python3Lexer.EXCEPT:
            continue
        except_line = tok.line
        j = _skip_to_colon(tokens, i + 1, n)
        if j >= n:
            continue
        k = j + 1
        while k < n and tokens[k].type in (Python3Lexer.NEWLINE, Python3Lexer.INDENT):
            k += 1
        if k < n and tokens[k].type in (Python3Lexer.PASS, Python3Lexer.ELLIPSIS):
            smells.append(
                Smell.create(
                    SmellType.EMPTY_CATCH_CLAUSE,
                    fp,
                    except_line,
                    "<except>",
                    "Exception handler body is empty (pass or ...)",
                )
            )
    return smells


def _skip_to_colon(tokens: list, start: int, n: int) -> int:
    j = start
    paren_depth = 0
    while j < n:
        t = tokens[j]
        if t.type in (Python3Lexer.OPEN_PAREN, Python3Lexer.OPEN_BRACK):
            paren_depth += 1
        elif t.type in (Python3Lexer.CLOSE_PAREN, Python3Lexer.CLOSE_BRACK):
            paren_depth -= 1
        elif t.type == Python3Lexer.COLON and paren_depth == 0:
            break
        j += 1
    return j


def _detect_complex_conditionals(fp: str, tokens: list) -> list[Smell]:
    smells: list[Smell] = []
    n = len(tokens)
    seen_lines: set[int] = set()
    i = 0
    while i < n:
        tok = tokens[i]
        if tok.type not in (Python3Lexer.IF, Python3Lexer.ELIF):
            i += 1
            continue
        start_line = tok.line
        if start_line in seen_lines:
            i += 1
            continue
        j, bool_ops = _count_bool_ops(tokens, i + 1, n)
        if bool_ops >= COMPLEX_CONDITIONAL_BOOLEAN_OPS:
            seen_lines.add(start_line)
            smells.append(
                Smell.create(
                    SmellType.COMPLEX_CONDITIONAL,
                    fp,
                    start_line,
                    "<conditional>",
                    "Conditional has 4+ boolean operators — consider simplifying",
                )
            )
        i = j + 1
    return smells


def _count_bool_ops(tokens: list, start: int, n: int) -> tuple[int, int]:
    j = start
    paren_depth = 0
    bool_ops = 0
    while j < n:
        t = tokens[j]
        if t.type in (Python3Lexer.OPEN_PAREN, Python3Lexer.OPEN_BRACK):
            paren_depth += 1
        elif t.type in (Python3Lexer.CLOSE_PAREN, Python3Lexer.CLOSE_BRACK):
            paren_depth -= 1
        elif t.type in (Python3Lexer.AND, Python3Lexer.OR) and paren_depth == 0:
            bool_ops += 1
        elif t.type == Python3Lexer.COLON and paren_depth == 0:
            break
        elif t.type == Python3Lexer.NEWLINE and paren_depth == 0:
            break
        j += 1
    return j, bool_ops


def _detect_missing_default(fp: str, tokens: list) -> list[Smell]:
    smells: list[Smell] = []
    n = len(tokens)
    i = 0
    while i < n:
        if tokens[i].type != Python3Lexer.MATCH:
            i += 1
            continue
        match_line = tokens[i].line
        j = i + 1
        while j < n and tokens[j].type != Python3Lexer.COLON:
            j += 1
        j += 1
        while j < n and tokens[j].type in (Python3Lexer.NEWLINE, Python3Lexer.INDENT):
            j += 1
        has_wildcard, k = _scan_case_blocks(tokens, j, n)
        if not has_wildcard:
            smells.append(
                Smell.create(
                    SmellType.MISSING_DEFAULT,
                    fp,
                    match_line,
                    "<match>",
                    "Match statement has no default 'case _' clause",
                )
            )
        i = k
    return smells


def _scan_case_blocks(tokens: list, start: int, n: int) -> tuple[bool, int]:
    has_wildcard = False
    depth = 1
    k = start
    while k < n and depth > 0:
        t = tokens[k]
        if t.type == Python3Lexer.INDENT:
            depth += 1
        elif t.type == Python3Lexer.DEDENT:
            depth -= 1
            if depth == 0:
                k += 1
                break
        elif (
            t.type == Python3Lexer.CASE
            and depth == 1
            and k + 1 < n
            and tokens[k + 1].type == Python3Lexer.UNDERSCORE
        ):
            has_wildcard = True
        k += 1
    return has_wildcard, k


def _count_dot_chain(tokens: list, start: int, n: int) -> tuple[int, int]:
    j = start
    dot_count = 0
    while (
        j + 1 < n
        and tokens[j].type == Python3Lexer.DOT
        and tokens[j + 1].type == Python3Lexer.NAME
    ):
        dot_count += 1
        j += 2
    return j, dot_count


def _detect_long_message_chains(fp: str, tokens: list) -> list[Smell]:
    smells: list[Smell] = []
    n = len(tokens)
    seen_lines: set[int] = set()
    i = 0
    while i < n - 2:
        tok = tokens[i]
        if tok.type != Python3Lexer.NAME:
            i += 1
            continue
        j, dot_count = _count_dot_chain(tokens, i + 1, n)
        if dot_count >= LONG_MESSAGE_CHAIN_DOTS:
            line = tok.line
            if line not in seen_lines:
                seen_lines.add(line)
                smells.append(
                    Smell.create(
                        SmellType.LONG_MESSAGE_CHAIN,
                        fp,
                        line,
                        "<line>",
                        f"Message chain has {dot_count} dot accesses (threshold {LONG_MESSAGE_CHAIN_DOTS})",
                    )
                )
        i += 1
    return smells


# ---------------------------------------------------------------------------
# Magic number detection
# ---------------------------------------------------------------------------


def _build_const_lines(tokens: list) -> set[int]:
    const_lines: set[int] = set()
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok.type != Python3Lexer.NAME:
            continue
        text = tok.text
        if not (text[0].isalpha() and text[0].isupper() and text.upper() == text):
            continue
        j = i + 1
        while j < n and tokens[j].type in (Python3Lexer.INDENT, Python3Lexer.DEDENT):
            j += 1
        if j < n and tokens[j].type == Python3Lexer.ASSIGN:
            const_lines.add(tok.line)
    return const_lines


def _find_containing_func(data: AnalysisData | None, line_no: int) -> str:
    if data is None:
        return "<module>"
    all_funcs = list(data.top_level_functions)
    for cls in data.classes:
        all_funcs.extend(cls.methods)
    for fn in all_funcs:
        if fn.line_start <= line_no <= fn.line_end:
            return fn.name
    return "<module>"


def _detect_magic_numbers(
    fp: str,
    data: AnalysisData,
    tokens: list,
) -> list[Smell]:
    smells: list[Smell] = []
    const_lines = _build_const_lines(tokens)

    for token in tokens:
        if token.type == -1 or token.type != Python3Lexer.NUMBER:
            continue
        line_no = token.line
        num_text = token.text.strip()
        if num_text in WHITELISTED_NUMBERS:
            continue
        if line_no in const_lines:
            continue
        element = _find_containing_func(data, line_no)
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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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
