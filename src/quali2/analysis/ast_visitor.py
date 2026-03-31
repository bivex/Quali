"""AST-based visitor that extracts structural code data using Python's ast module."""

from __future__ import annotations

import ast

from quali2.domain.models import (
    AnalysisData,
    ClassInfo,
    ImportInfo,
    MethodInfo,
    ParamInfo,
)


class AstCodeVisitor(ast.NodeVisitor):
    """Walks a Python ast tree and populates an AnalysisData structure."""

    def __init__(self, file_path: str, source_lines: list[str]) -> None:
        self.data = AnalysisData(file_path=file_path, total_lines=len(source_lines))
        self._source_lines = source_lines
        self._class_stack: list[ClassInfo] = []
        self._method_stack: list[MethodInfo] = []
        self._class_map: dict[str, ClassInfo] = {}

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.data.imports.append(
                ImportInfo(module=alias.name, alias=alias.asname, line=node.lineno)
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        names = [a.name for a in node.names]
        self.data.imports.append(ImportInfo(module=mod, names=names, line=node.lineno))
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)

    def _process_function(self, node) -> None:
        name = node.name
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", node.lineno)
        params = [ParamInfo(name=arg.arg) for arg in node.args.args]
        cc = _calc_cyclomatic(node)

        mi = MethodInfo(
            name=name,
            line_start=line_start,
            line_end=line_end,
            params=params,
            cyclomatic_complexity=cc,
            num_statements=line_end - line_start + 1,
        )

        if self._class_stack:
            cls = self._class_stack[-1]
            cls.methods.append(mi)
            if name == "__init__":
                for attr_name in _collect_self_attr_refs(node):
                    cls.fields.add(attr_name)
        else:
            self.data.top_level_functions.append(mi)

        self._method_stack.append(mi)
        self.generic_visit(node)
        self._method_stack.pop()

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = node.name
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", node.lineno)

        bases: list[str] = []
        for base in node.bases:
            bases.append(_ast_name(base))

        decorators = [_ast_name(d) for d in node.decorator_list]

        depth = _inheritance_depth(bases, self._class_map)
        ci = ClassInfo(
            name=name,
            line_start=line_start,
            line_end=line_end,
            bases=bases,
            decorators=decorators,
            depth_inheritance=depth,
        )

        self.data.classes.append(ci)
        self._class_map[name] = ci
        self._class_stack.append(ci)
        self.generic_visit(node)
        self._class_stack.pop()

    # ------------------------------------------------------------------
    # Attribute access tracking
    # ------------------------------------------------------------------

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            self._method_stack
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            self._method_stack[-1].accesses_attrs.add(node.attr)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ast_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _ast_name(node.value) + "." + node.attr
    if isinstance(node, ast.Subscript):
        return _ast_name(node.value)
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Call):
        return _ast_name(node.func)
    return "<?>"


def _inheritance_depth(bases: list[str], class_map: dict[str, ClassInfo]) -> int:
    if not bases or bases == ["object"]:
        return 0
    max_depth = 0
    for b in bases:
        if b in class_map:
            max_depth = max(max_depth, class_map[b].depth_inheritance + 1)
        else:
            max_depth = max(max_depth, 1)
    return max_depth


def _calc_cyclomatic(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
    return complexity


def _collect_self_attr_refs(node: ast.AST) -> set[str]:
    refs: set[str] = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
        ):
            refs.add(child.attr)
    return refs
