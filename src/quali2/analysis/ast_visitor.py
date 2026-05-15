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
        super().__init__()
        self.data = AnalysisData(file_path=file_path, total_lines=len(source_lines))
        self._source_lines = source_lines
        self._class_stack: list[ClassInfo] = []
        self._method_stack: list[MethodInfo] = []
        # Persistent state for inheritance tracking within the same file
        self._seen_classes: dict[str, ClassInfo] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.data.imports.append(
                ImportInfo(module=alias.name, alias=alias.asname, line=node.lineno)
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.data.imports.append(
                ImportInfo(module=node.module, alias=None, line=node.lineno)
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = node.name
        params = [ParamInfo(name=arg.arg) for arg in node.args.args]
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", line_start)

        # Basic complexity: start with 1, add for branches
        cc = _calc_cyclomatic(node)

        mi = MethodInfo(
            name=name,
            params=params,
            line_start=line_start,
            line_end=line_end,
            num_statements=len(node.body),
            cyclomatic_complexity=cc,
        )

        # Track attribute accesses
        mi.accesses_attrs.update(_collect_self_attr_refs(node))

        if self._class_stack:
            self._class_stack[-1].methods.append(mi)
        else:
            self.data.top_level_functions.append(mi)

        self._method_stack.append(mi)
        self.generic_visit(node)
        self._method_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = node.name
        bases = [_ast_name(b) for b in node.bases]
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", line_start)

        depth = _inheritance_depth(bases, self._seen_classes)

        ci = ClassInfo(
            name=name,
            bases=bases,
            line_start=line_start,
            line_end=line_end,
            depth_inheritance=depth,
        )

        # Extract fields (assignments to self.x in __init__)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "__init__":
                for stmt in child.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                                ci.fields.add(target.attr)

        self.data.classes.append(ci)
        self._seen_classes[name] = ci
        self._class_stack.append(ci)
        self.generic_visit(node)
        self._class_stack.pop()

    # ------------------------------------------------------------------
    # Attribute access tracking
    # ------------------------------------------------------------------

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self._method_stack:
            self._method_stack[-1].accesses_attrs.add(node.attr)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ast_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_ast_name(node.value)}.{node.attr}"
    return "object"


def _inheritance_depth(bases: list[str], class_map: dict[str, ClassInfo]) -> int:
    if not bases:
        return 0
    max_d = 0
    for b in bases:
        if b in class_map:
            max_d = max(max_d, class_map[b].depth_inheritance + 1)
        else:
            # External or object
            max_d = max(max_d, 1)
    return max_d


def _calc_cyclomatic(node: ast.AST) -> int:
    cc = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
            cc += 1
        elif isinstance(child, ast.BoolOp):
            cc += len(child.values) - 1
    return cc


def _collect_self_attr_refs(node: ast.AST) -> set[str]:
    refs = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
        ):
            refs.add(child.attr)
    return refs
