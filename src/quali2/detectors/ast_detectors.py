"""AST-based smell detectors — replacements for token-stream based detectors."""

from __future__ import annotations

import ast

from quali2.domain.models import AnalysisData, Smell, SmellType

# Import thresholds from existing detectors
from quali2.detectors.implementation import (
    COMPLEX_CONDITIONAL_BOOLEAN_OPS,
    LONG_LAMBDA_LINES,
    LONG_MESSAGE_CHAIN_DOTS,
    WHITELISTED_NUMBERS,
)
from quali2.detectors.ml import _check_line_smells as _ml_line_smells


# ---------------------------------------------------------------------------
# Implementation: AST-based detectors
# ---------------------------------------------------------------------------


def ast_detect_empty_catch_clauses(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if _is_empty_handler(handler):
                smells.append(
                    Smell.create(
                        SmellType.EMPTY_CATCH_CLAUSE,
                        fp,
                        handler.lineno,
                        "<except>",
                        "Exception handler body is empty (pass or ...)",
                    )
                )
    return smells


def _is_empty_handler(handler: ast.ExceptHandler) -> bool:
    if len(handler.body) == 1:
        stmt = handler.body[0]
        if isinstance(stmt, ast.Pass):
            return True
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value is ...
        ):
            return True
    return False


def ast_detect_magic_numbers(
    fp: str, data: AnalysisData, tree: ast.AST, source: str = ""
) -> list[Smell]:
    const_lines = _find_const_assignment_lines(tree)
    all_funcs = list(data.top_level_functions)
    for cls in data.classes:
        all_funcs.extend(cls.methods)

    source_lines = source.splitlines() if source else []
    smells: list[Smell] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Constant)
            or not isinstance(node.value, (int, float))
            or isinstance(node.value, bool)
        ):
            continue
        if node.lineno in const_lines:
            continue
        text = _number_text(node, source_lines)
        if text in WHITELISTED_NUMBERS:
            continue
        elem = _find_containing_func(all_funcs, node.lineno)
        smells.append(
            Smell.create(
                SmellType.MAGIC_NUMBER,
                fp,
                node.lineno,
                elem,
                f"Magic number '{text}' — consider extracting to a named constant",
            )
        )
    return smells


def _number_text(node: ast.Constant, source_lines: list[str]) -> str:
    if source_lines and 0 < node.lineno <= len(source_lines):
        line = source_lines[node.lineno - 1]
        col = node.col_offset
        end_col = getattr(node, "end_col_offset", col + 10)
        if end_col <= len(line):
            return line[col:end_col]
    return repr(node.value)


def _find_const_assignment_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                lines.add(target.lineno)
    return lines


def _find_containing_func(all_funcs: list, line_no: int) -> str:
    for fn in all_funcs:
        if fn.line_start <= line_no <= fn.line_end:
            return fn.name
    return "<module>"


def ast_detect_complex_conditionals(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.While)):
            continue
        bool_count = _count_bool_ops(node.test)
        if (
            bool_count >= COMPLEX_CONDITIONAL_BOOLEAN_OPS
            and node.lineno not in seen_lines
        ):
            seen_lines.add(node.lineno)
            smells.append(
                Smell.create(
                    SmellType.COMPLEX_CONDITIONAL,
                    fp,
                    node.lineno,
                    "<conditional>",
                    "Conditional has 4+ boolean operators — consider simplifying",
                )
            )
    return smells


def _count_bool_ops(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
    return count


def ast_detect_missing_default(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Match):
            continue
        has_wildcard = any(
            isinstance(case.pattern, MatchAs) and case.pattern.pattern is None
            for case in node.cases
        )
        if not has_wildcard:
            smells.append(
                Smell.create(
                    SmellType.MISSING_DEFAULT,
                    fp,
                    node.lineno,
                    "<match>",
                    "Match statement has no default 'case _' clause",
                )
            )
    return smells


# Use MatchAs from ast — but guard for Python < 3.10
try:
    MatchAs = ast.MatchAs
except AttributeError:
    MatchAs = type(None)  # fallback: will never match


def ast_detect_long_message_chains(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = _count_attr_chain(node)
        if chain >= LONG_MESSAGE_CHAIN_DOTS and node.lineno not in seen_lines:
            seen_lines.add(node.lineno)
            smells.append(
                Smell.create(
                    SmellType.LONG_MESSAGE_CHAIN,
                    fp,
                    node.lineno,
                    "<line>",
                    f"Message chain has {chain} dot accesses (threshold {LONG_MESSAGE_CHAIN_DOTS})",
                )
            )
    return smells


def _count_attr_chain(node: ast.AST) -> int:
    count = 0
    while isinstance(node, ast.Attribute):
        count += 1
        node = node.value
    return count - 1  # don't count the base name


def ast_detect_long_lambdas(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Lambda):
            continue
        end = getattr(node.body, "end_lineno", node.lineno)
        span = end - node.lineno + 1
        if span > LONG_LAMBDA_LINES:
            smells.append(
                Smell.create(
                    SmellType.LONG_LAMBDA_FUNCTION,
                    fp,
                    node.lineno,
                    "<lambda>",
                    f"Lambda spans {span} lines (threshold {LONG_LAMBDA_LINES})",
                )
            )
    return smells


# ---------------------------------------------------------------------------
# ML: AST-based detectors
# ---------------------------------------------------------------------------


def ast_detect_broken_nan(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for comparator in node.comparators:
            if _is_nan_ast(comparator) and node.lineno not in seen_lines:
                seen_lines.add(node.lineno)
                smells.append(
                    Smell.create(
                        SmellType.BROKEN_NAN_CHECK,
                        fp,
                        node.lineno,
                        "<line>",
                        "Direct comparison with NaN always returns False — use math.isnan() or pd.isna()",
                    )
                )
    return smells


def _is_nan_ast(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id in ("nan", "NaN"):
        return True
    if _is_dotted_nan_ast(node):
        return True
    if _is_float_nan_ast(node):
        return True
    return False


def _is_dotted_nan_ast(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "nan"
        and isinstance(node.value, ast.Name)
        and node.value.id in ("float", "math", "np", "numpy")
    )


def _is_float_nan_ast(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    if node.func.id != "float" or len(node.args) != 1:
        return False
    return (
        isinstance(node.args[0], ast.Constant)
        and "nan" in str(node.args[0].value).lower()
    )


def ast_detect_chain_indexing(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        if isinstance(node.value, ast.Subscript) and node.lineno not in seen_lines:
            seen_lines.add(node.lineno)
            smells.append(
                Smell.create(
                    SmellType.CHAIN_INDEXING,
                    fp,
                    node.lineno,
                    "<line>",
                    "Chained indexing on DataFrame: df[...][...] — use .loc[] instead",
                )
            )
    return smells


def ast_detect_unnecessary_iteration(fp: str, tree: ast.AST) -> list[Smell]:
    iter_methods = frozenset({"iterrows", "itertuples"})
    smells: list[Smell] = []
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        iter_node = node.iter
        if (
            isinstance(iter_node, ast.Call)
            and isinstance(iter_node.func, ast.Attribute)
            and iter_node.func.attr in iter_methods
            and node.lineno not in seen_lines
        ):
            seen_lines.add(node.lineno)
            smells.append(
                Smell.create(
                    SmellType.UNNECESSARY_ITERATION,
                    fp,
                    node.lineno,
                    "<line>",
                    "Iterating over DataFrame — prefer vectorized operations",
                )
            )
    return smells


def ast_detect_forward_bypass(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    seen_lines: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "forward"
            and node.lineno not in seen_lines
        ):
            seen_lines.add(node.lineno)
            smells.append(
                Smell.create(
                    SmellType.FORWARD_BYPASS,
                    fp,
                    node.lineno,
                    "<line>",
                    "Calling .forward() directly — use model(input) instead to trigger hooks",
                )
            )
    return smells


def ast_detect_ambiguous_merge_key(fp: str, source: str) -> list[Smell]:
    """Line-based check — same as ANTLR version."""
    return _ml_line_smells(fp, source.splitlines(), uses_pandas=True)
