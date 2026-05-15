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

    def __init__(self, file_path, source_lines):
        super().__init__()
        self.data = AnalysisData(file_path=file_path, total_lines=len(source_lines))
        self._source_lines = source_lines
        self._class_stack = []
        self._method_stack = []

    def visit_Import(self, node):
        _process_imports(self.data, node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        _process_import_from(self.data, node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._process_function(node)

    def _process_function(self, node):
        mi = _build_method_info(node)
        _register_method(self.data, self._class_stack, mi)
        self._method_stack.append(mi)
        self.generic_visit(node)
        self._method_stack.pop()

    def visit_ClassDef(self, node):
        _process_class(self.data, self._class_stack, node)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_Attribute(self, node):
        _track_attr_access(self._method_stack, node)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Pure helpers (module-level — no self → no Feature Envy possible)
# ---------------------------------------------------------------------------


def _process_imports(data, node):
    for alias in node.names:
        data.add_import(
            ImportInfo(module=alias.name, alias=alias.asname, line=node.lineno)
        )


def _process_import_from(data, node):
    if node.module:
        data.add_import(
            ImportInfo(module=node.module, alias=None, line=node.lineno)
        )


def _register_method(data, class_stack, mi):
    if class_stack:
        class_stack[-1].methods.append(mi)
    else:
        data.add_function(mi)


def _track_attr_access(stack, node):
    if stack:
        stack[-1].accesses_attrs.add(node.attr)


def _process_class(data, class_stack, node):
    seen = {c.name: c for c in data.classes}
    ci = _build_class_info(node, seen)
    _extract_fields_from_init(node, ci)
    data.add_class(ci)
    class_stack.append(ci)


def _ast_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_ast_name(node.value)}.{node.attr}"
    return "object"


def _inheritance_depth(bases, class_map):
    if not bases:
        return 0
    max_d = 0
    for b in bases:
        if b in class_map:
            max_d = max(max_d, class_map[b].depth_inheritance + 1)
        else:
            max_d = max(max_d, 1)
    return max_d


def _calc_cyclomatic(node):
    cc = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
            cc += 1
        elif isinstance(child, ast.BoolOp):
            cc += len(child.values) - 1
    return cc


def _collect_self_attr_refs(node):
    refs = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
        ):
            refs.add(child.attr)
    return refs


def _build_method_info(node):
    params = [ParamInfo(name=arg.arg) for arg in node.args.args]
    line_end = getattr(node, "end_lineno", node.lineno)
    cc = _calc_cyclomatic(node)
    mi = MethodInfo(
        name=node.name,
        params=params,
        line_start=node.lineno,
        line_end=line_end,
        num_statements=len(node.body),
        cyclomatic_complexity=cc,
    )
    mi.accesses_attrs.update(_collect_self_attr_refs(node))
    return mi


def _build_class_info(node, seen):
    bases = [_ast_name(b) for b in node.bases]
    line_end = getattr(node, "end_lineno", node.lineno)
    depth = _inheritance_depth(bases, seen)
    return ClassInfo(
        name=node.name,
        bases=bases,
        line_start=node.lineno,
        line_end=line_end,
        depth_inheritance=depth,
    )


def _extract_fields_from_init(node, ci):
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "__init__":
            for stmt in child.body:
                targets = []
                if isinstance(stmt, ast.Assign):
                    targets = stmt.targets
                elif isinstance(stmt, ast.AnnAssign) and stmt.target:
                    targets = [stmt.target]
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        ci.fields.add(target.attr)
