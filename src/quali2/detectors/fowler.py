"""Fowler's Refactoring code smell detectors.

Implements detectors for:
1.  Switch Statements
2.  Message Chains (bridged to existing)
3.  Data Clumps
4.  Feature Envy (bridged to existing)
5.  Primitive Obsession
6.  Middle Man
7.  Speculative Generality
8.  Divergent Change
9.  Shotgun Surgery
10. Temporary Field
11. Refused Bequest
12. Comment Density
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass

from quali2.domain.models import AnalysisData, Smell, SmellType

# Thresholds
SWITCH_STATEMENT_CASES = 5
DATA_CLUMP_PARAMS = 3
DATA_CLUMP_OCCURRENCES = 2
PRIMITIVE_OBSESSION_PARAMS = 5
MIDDLE_MAN_RATIO = 0.5
COMMENT_DENSITY_THRESHOLD = 0.3
LCOM_RISK_THRESHOLD = 0.8


@dataclass
class FowlerContext:
    """Consolidates parameters for Fowler detectors to avoid Data Clumps."""

    data: AnalysisData
    tree: ast.AST
    source: str


def detect_fowler_smells(data: AnalysisData, tree: ast.AST, source: str) -> list[Smell]:
    ctx = FowlerContext(data, tree, source)
    smells: list[Smell] = []
    fp = data.file_path

    # AST-based checks
    smells.extend(_detect_switch_statements(fp, tree))
    smells.extend(_detect_primitive_obsession(fp, tree))
    smells.extend(_detect_middle_man(ctx))
    smells.extend(_detect_temporary_fields(ctx))
    smells.extend(_detect_refused_bequest(fp, tree))
    smells.extend(_detect_speculative_generality(fp, tree))

    # Data/Metric based checks
    smells.extend(_detect_data_clumps(fp, data))
    smells.extend(_detect_comment_density(fp, source))

    # Divergent Change & Shotgun Surgery (Heuristics)
    smells.extend(_detect_divergent_change(fp, data))
    smells.extend(_detect_shotgun_surgery(fp, data))

    return smells


def _detect_switch_statements(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    for node in ast.walk(tree):
        # Python 3.10+ match statement
        match_cls = getattr(ast, "Match", type(None))
        if isinstance(node, match_cls):
            if len(node.cases) > SWITCH_STATEMENT_CASES:
                smells.append(
                    Smell.create(
                        SmellType.SWITCH_STATEMENTS,
                        fp,
                        node.lineno,
                        "<match>",
                        f"Match statement has {len(node.cases)} cases (threshold {SWITCH_STATEMENT_CASES})",
                    )
                )

        # Long if-elif chains
        if isinstance(node, ast.If):
            # Only check top-level if of a chain
            if _is_elif(node):
                continue
            count = _count_elif_chain(node)
            if count > SWITCH_STATEMENT_CASES:
                smells.append(
                    Smell.create(
                        SmellType.SWITCH_STATEMENTS,
                        fp,
                        node.lineno,
                        "<if-elif>",
                        f"If-elif chain has {count} branches (threshold {SWITCH_STATEMENT_CASES})",
                    )
                )
    return smells


def _is_elif(node: ast.If) -> bool:
    """Check if this If node is actually an 'elif'."""
    return hasattr(node, "is_elif") and getattr(node, "is_elif")


def _count_elif_chain(node: ast.If) -> int:
    count = 1
    current = node
    while len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
        count += 1
        current = current.orelse[0]
        # Mark child as elif to avoid double counting
        setattr(current, "is_elif", True)
    if current.orelse:
        count += 1
    return count


def _detect_primitive_obsession(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            primitives = 0
            for arg in node.args.args:
                # We can't always know the type, but we can look at defaults or annotations
                if arg.annotation:
                    if _is_primitive_annotation(arg.annotation):
                        primitives += 1
                elif _has_primitive_default(node, arg):
                    primitives += 1

            if primitives >= PRIMITIVE_OBSESSION_PARAMS:
                smells.append(
                    Smell.create(
                        SmellType.PRIMITIVE_OBSESSION,
                        fp,
                        node.lineno,
                        node.name,
                        f"Function has {primitives} primitive parameters — consider using a data class",
                    )
                )
    return smells


def _is_primitive_annotation(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in ("int", "float", "str", "bool", "bytes")
    return False


def _has_primitive_default(func: ast.FunctionDef, arg: ast.arg) -> bool:
    # Match arg to its default
    args = func.args.args
    defaults = func.args.defaults
    offset = len(args) - len(defaults)
    try:
        idx = args.index(arg)
        if idx >= offset:
            default = defaults[idx - offset]
            return isinstance(default, ast.Constant) and isinstance(
                default.value, (int, float, str, bool, bytes)
            )
    except (ValueError, IndexError):
        # Param not found in args or defaults index out of range — skip
        return False
    return False


def _detect_data_clumps(fp: str, data: AnalysisData) -> list[Smell]:
    smells: list[Smell] = []
    funcs = list(data.top_level_functions)
    for cls in data.classes:
        funcs.extend(cls.methods)

    # Filter out functions with too few params to even be part of a clump
    clump_candidates = [f for f in funcs if len(f.params) >= DATA_CLUMP_PARAMS]

    flagged_funcs = set()
    for i in range(len(clump_candidates)):
        for j in range(i + 1, len(clump_candidates)):
            f1 = clump_candidates[i]
            f2 = clump_candidates[j]

            p1 = {p.name for p in f1.params if p.name not in ("self", "cls")}
            p2 = {p.name for p in f2.params if p.name not in ("self", "cls")}

            common = p1 & p2
            if len(common) >= DATA_CLUMP_PARAMS:
                # Found a clump between f1 and f2
                for f in (f1, f2):
                    key = (f.name, f.line_start)
                    if key not in flagged_funcs:
                        flagged_funcs.add(key)
                        other_name = f2.name if f == f1 else f1.name
                        smells.append(
                            Smell.create(
                                SmellType.DATA_CLUMPS,
                                fp,
                                f.line_start,
                                f.name,
                                f"Shared parameters {sorted(list(common))} suggest a Data Clump with '{other_name}'",
                            )
                        )
    return smells


def _detect_middle_man(ctx: FowlerContext) -> list[Smell]:
    smells: list[Smell] = []
    fp = ctx.data.file_path
    for cls_info in ctx.data.classes:
        # Find class node in AST
        cls_node = None
        for node in ast.walk(ctx.tree):
            if isinstance(node, ast.ClassDef) and node.name == cls_info.name:
                cls_node = node
                break

        if not cls_node:
            continue

        methods = [n for n in cls_node.body if isinstance(n, ast.FunctionDef)]
        if not methods:
            continue

        delegates = 0
        for m in methods:
            if _is_delegation(m):
                delegates += 1

        if len(methods) > 3 and (delegates / len(methods)) >= MIDDLE_MAN_RATIO:
            smells.append(
                Smell.create(
                    SmellType.MIDDLE_MAN,
                    fp,
                    cls_info.line_start,
                    f"class {cls_info.name}",
                    f"Class is a Middle Man: {delegates}/{len(methods)} methods just delegate calls",
                )
            )
    return smells


def _is_delegation(node: ast.FunctionDef) -> bool:
    """Check if method body is just 'return self.x.y(*args, **kwargs)' or similar."""
    if len(node.body) != 1:
        return False
    stmt = node.body[0]
    if isinstance(stmt, ast.Return) and stmt.value:
        return _is_call_to_other(stmt.value)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _is_call_to_other(stmt.value)
    return False


def _is_call_to_other(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    # self.other.method()
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        if isinstance(func.value.value, ast.Name) and func.value.value.id == "self":
            return True
    return False


def _detect_speculative_generality(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    # 1. Unused parameters
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("__"):
                continue
            used_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            for arg in node.args.args:
                if arg.arg not in ("self", "cls") and arg.arg not in used_names:
                    smells.append(
                        Smell.create(
                            SmellType.SPECULATIVE_GENERALITY,
                            fp,
                            arg.lineno,
                            node.name,
                            f"Unused parameter '{arg.arg}'",
                        )
                    )
    return smells


def _detect_temporary_fields(ctx: FowlerContext) -> list[Smell]:
    smells: list[Smell] = []
    fp = ctx.data.file_path
    for cls_info in ctx.data.classes:
        if not cls_info.fields:
            continue

        field_usage = {f: set() for f in cls_info.fields}
        for m in cls_info.methods:
            for attr in m.accesses_attrs:
                if attr in field_usage:
                    field_usage[attr].add(m.name)

        for field, methods in field_usage.items():
            # If used in only one method (and it's not __init__ or used in only __init__)
            # then it might be a temporary field.
            methods.discard("__init__")
            if len(methods) == 1:
                smells.append(
                    Smell.create(
                        SmellType.TEMPORARY_FIELD,
                        fp,
                        cls_info.line_start,
                        f"class {cls_info.name}",
                        f"Attribute '{field}' is only used in method '{list(methods)[0]}'",
                    )
                )
    return smells


def _detect_refused_bequest(fp: str, tree: ast.AST) -> list[Smell]:
    smells: list[Smell] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check for raising NotImplementedError
            if len(node.body) == 1:
                stmt = node.body[0]
                if isinstance(stmt, ast.Raise):
                    if isinstance(stmt.exc, ast.Call) and isinstance(
                        stmt.exc.func, ast.Name
                    ):
                        if stmt.exc.func.id == "NotImplementedError":
                            smells.append(
                                Smell.create(
                                    SmellType.REFUSED_BEQUEST,
                                    fp,
                                    node.lineno,
                                    node.name,
                                    "Method raises NotImplementedError — may be refusing inherited behavior",
                                )
                            )
    return smells


def _detect_comment_density(fp: str, source: str) -> list[Smell]:
    smells: list[Smell] = []
    lines = source.splitlines()
    total_loc = len(lines)
    if total_loc < 5:
        return []

    comment_lines = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            comment_lines += 1

    density = comment_lines / total_loc
    if density > COMMENT_DENSITY_THRESHOLD:
        smells.append(
            Smell.create(
                SmellType.COMMENT_DENSITY,
                fp,
                1,
                "<file>",
                f"High comment density ({density:.2%}) — code should be self-documenting",
            )
        )
    return smells


def _detect_divergent_change(fp: str, data: AnalysisData) -> list[Smell]:
    """Heuristic: Class with high NOM and low cohesion (LCOM)."""
    smells: list[Smell] = []
    for cls in data.classes:
        # LCOM calculation from metrics.py
        lcom = _calc_lcom(cls)
        if len(cls.methods) > 10 and lcom > LCOM_RISK_THRESHOLD:
            smells.append(
                Smell.create(
                    SmellType.DIVERGENT_CHANGE,
                    fp,
                    cls.line_start,
                    f"class {cls.name}",
                    f"High Divergent Change risk: {len(cls.methods)} methods and low cohesion (LCOM={lcom:.2f})",
                )
            )
    return smells


def _calc_lcom(cls) -> float:
    # Simplified LCOM from metrics.py
    methods = [m for m in cls.methods if not m.name.startswith("__")]
    if len(methods) < 2 or not cls.fields:
        return 0.0
    n = len(methods)
    p = 0
    q = 0
    for i in range(n):
        for j in range(i + 1, n):
            shared = methods[i].accesses_attrs & methods[j].accesses_attrs
            if shared:
                q += 1
            else:
                p += 1
    total = p + q
    return (p - q) / total if total > 0 else 0.0


def _detect_shotgun_surgery(fp: str, data: AnalysisData) -> list[Smell]:
    """Heuristic: Method that accesses many different classes' attributes."""
    smells: list[Smell] = []
    for cls in data.classes:
        for m in cls.methods:
            # This is hard because we don't know which attributes belong to which classes
            # without a symbol table. But we can look at the number of unique attribute
            # accesses that don't belong to the current class.
            external_accesses = m.accesses_attrs - cls.fields
            if len(external_accesses) > 10:
                smells.append(
                    Smell.create(
                        SmellType.SHOTGUN_SURGERY,
                        fp,
                        m.line_start,
                        f"{cls.name}.{m.name}",
                        f"Method accesses {len(external_accesses)} external attributes — high coupling",
                    )
                )
    return smells
