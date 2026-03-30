"""Implementation smell detectors.

Detects: Complex Conditional, Complex Method, Empty Catch Clause,
Long Identifier, Long Method, Long Parameter List, Long Statement,
Magic Number, Missing Default, Long Lambda Function, Long Message Chain.
"""

from __future__ import annotations

import re

from quali2.domain.models import AnalysisData, Smell, SmellType

LONG_METHOD_LINES = 40
LONG_PARAM_LIST = 7
COMPLEX_METHOD_CC = 15
COMPLEX_CONDITIONAL_BOOLEAN_OPS = 4
LONG_IDENTIFIER_CHARS = 40
LONG_STATEMENT_CHARS = 120
LONG_LAMBDA_LINES = 5
LONG_MESSAGE_CHAIN_DOTS = 4
MAGIC_NUMBER_PATTERN = re.compile(r"(?<![\w.])(\d{2,})\s*[+\-*/]")
EXCEPT_PATTERN = re.compile(
    r"except\s+[\w.]+(?:\s+as\s+\w+)?\s*:\s*(?:pass|\.\.\.)\s*$",
    re.MULTILINE,
)


def detect_implementation_smells(data: AnalysisData, source: str) -> list[Smell]:
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

    # Magic Numbers & Long Statements & Long Lambda & Long Message Chain & Complex Conditional
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

        # Magic Number (skip common acceptable values)
        for m in MAGIC_NUMBER_PATTERN.finditer(stripped):
            num = m.group(1)
            if num not in (
                "0",
                "1",
                "2",
                "100",
                "1000",
                "1024",
                "200",
                "201",
                "204",
                "400",
                "401",
                "403",
                "404",
                "500",
            ):
                if not _is_in_string_or_comment(stripped, m.start()):
                    smells.append(
                        Smell.create(
                            SmellType.MAGIC_NUMBER,
                            fp,
                            i,
                            "<line>",
                            f"Magic number '{num}' found",
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


def _is_in_string_or_comment(line: str, pos: int) -> bool:
    before = line[:pos]
    if before.count("'") % 2 != 0 or before.count('"') % 2 != 0:
        return True
    if "#" in before:
        return True
    return False


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
