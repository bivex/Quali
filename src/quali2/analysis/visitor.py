"""ANTLR4 parse-tree visitor that extracts structural code data for analysis."""

from __future__ import annotations

from antlr4 import ParserRuleContext

from quali2.antlr.Python3Parser import Python3Parser
from quali2.antlr.Python3ParserVisitor import Python3ParserVisitor
from quali2.domain.models import (
    AnalysisData,
    ClassInfo,
    ImportInfo,
    MethodInfo,
    ParamInfo,
)


class PythonAnalysisVisitor(Python3ParserVisitor):
    """Walks the ANTLR4 parse tree and populates an AnalysisData structure."""

    def __init__(self, file_path, source_lines):
        super().__init__()
        self.data = AnalysisData(file_path=file_path, total_lines=len(source_lines))
        self._source_lines = source_lines
        self._class_stack = []
        self._method_stack = []

    def visitFile_input(self, ctx):
        self.visitChildren(ctx)
        return self.data

    def visitImport_name(self, ctx):
        _handle_import_name(self.data, ctx)
        self.visitChildren(ctx)

    def visitImport_from(self, ctx):
        _handle_import_from(self.data, ctx)
        self.visitChildren(ctx)

    def visitFuncdef(self, ctx):
        mi = _build_func_info(ctx)
        _register_method(self.data, self._class_stack, mi)
        if self._class_stack and mi.name == "__init__":
            _extract_init_fields(ctx, self._class_stack[-1])
        self._method_stack.append(mi)
        self.visitChildren(ctx)
        self._method_stack.pop()

    def visitClassdef(self, ctx):
        _process_classdef(self.data, self._class_stack, ctx)
        self.visitChildren(ctx)
        self._class_stack.pop()

    def visitTry_stmt(self, ctx):
        self.visitChildren(ctx)

    def visitExpr_stmt(self, ctx):
        _collect_attr_accesses(self._method_stack, ctx)
        self.visitChildren(ctx)

    def visitAtom_expr(self, ctx):
        _collect_attr_accesses(self._method_stack, ctx)
        self.visitChildren(ctx)


# ---------------------------------------------------------------------------
# Module-level helpers — no self → no Feature Envy
# ---------------------------------------------------------------------------


def _text(ctx):
    if ctx is None:
        return ""
    return ctx.getText()


def _handle_import_name(data, ctx):
    dotted = ctx.dotted_as_names()
    if not dotted:
        return
    for dan in dotted.dotted_as_name():
        mod = _text(dan.dotted_name())
        alias = _text(dan.name()) if dan.name() else None
        data.add_import(ImportInfo(module=mod, alias=alias, line=ctx.start.line))


def _handle_import_from(data, ctx):
    mod = _text(ctx.dotted_name()) if ctx.dotted_name() else ""
    names = []
    if ctx.import_as_names():
        for ian in ctx.import_as_names().import_as_name():
            names.append(_text(ian.name(0)))
    elif ctx.STAR():
        names = ["*"]
    data.add_import(ImportInfo(module=mod, names=names, line=ctx.start.line))


def _register_method(data, class_stack, mi):
    if class_stack:
        class_stack[-1].methods.append(mi)
    else:
        data.add_function(mi)


def _build_func_info(ctx):
    name = _text(ctx.name())
    line_start = ctx.start.line
    line_end = ctx.stop.line
    params_ctx = ctx.parameters().typedargslist() if ctx.parameters() else None
    params = (
        [_text(t.name()) for t in params_ctx.tfpdef()] if params_ctx else []
    )
    cc = _calc_cyclomatic(ctx)
    return MethodInfo(
        name=name,
        line_start=line_start,
        line_end=line_end,
        params=[ParamInfo(name=p) for p in params],
        cyclomatic_complexity=cc,
        num_statements=line_end - line_start + 1,
    )


def _process_classdef(data, class_stack, ctx):
    seen = {c.name: c for c in data.classes}
    ci = _build_class_info(ctx, seen)
    data.add_class(ci)
    class_stack.append(ci)


def _build_class_info(ctx, class_map):
    name = _text(ctx.name())
    line_start = ctx.start.line
    line_end = ctx.stop.line
    bases = _collect_bases(ctx)
    decorators = _collect_decorators(ctx)
    depth = _inheritance_depth(bases, class_map)
    return ClassInfo(
        name=name,
        line_start=line_start,
        line_end=line_end,
        bases=bases,
        decorators=decorators,
        depth_inheritance=depth,
    )


def _collect_bases(ctx):
    bases = []
    if ctx.arglist():
        for arg in ctx.arglist().argument():
            tests = arg.test()
            if tests:
                first_test = tests[0] if isinstance(tests, list) else tests
                bases.append(_text(first_test))
    return bases


def _collect_decorators(ctx):
    decorators = []
    parent = ctx.parentCtx
    if isinstance(parent, Python3Parser.DecoratedContext):
        for dec in parent.decorators().decorator():
            decorators.append(_text(dec.dotted_name()))
    return decorators


def _extract_init_fields(ctx, ci):
    refs = []
    _collect_self_refs(ctx, refs)
    for attr_name in set(refs):
        ci.fields.add(attr_name)


def _collect_attr_accesses(stack, ctx):
    if not stack:
        return
    text = _text(ctx)
    if ".self" in text or text.startswith("self."):
        parts = text.split(".")
        if len(parts) > 1 and parts[0] == "self":
            attr = parts[1].split("(")[0].split("[")[0]
            stack[-1].accesses_attrs.add(attr)


def _collect_self_refs(ctx, refs):
    text = _text(ctx)
    if "self." in text:
        for part in text.split("self.")[1:]:
            attr = (
                part.split("(")[0]
                .split("[")[0]
                .split(".")[0]
                .split(")")[0]
                .split(" ")[0]
            )
            if attr and attr.isidentifier():
                refs.append(attr)
    for child in ctx.getChildren():
        if isinstance(child, ParserRuleContext):
            _collect_self_refs(child, refs)


def _inheritance_depth(bases, class_map):
    if not bases or bases == ["object"]:
        return 0
    max_depth = 0
    for b in bases:
        if b in class_map:
            max_depth = max(max_depth, class_map[b].depth_inheritance + 1)
        else:
            max_depth = max(max_depth, 1)
    return max_depth


def _calc_cyclomatic(ctx):
    complexity = 1
    complexity += _count_nodes(
        ctx,
        (
            Python3Parser.If_stmtContext,
            Python3Parser.While_stmtContext,
            Python3Parser.For_stmtContext,
            Python3Parser.Except_clauseContext,
        ),
    )
    text = _text(ctx)
    complexity += text.count(" and ") + text.count(" or ")
    return complexity


def _count_nodes(ctx, node_types):
    count = 0
    for t in node_types:
        if isinstance(ctx, t):
            count += 1
    for child in ctx.getChildren():
        if isinstance(child, ParserRuleContext):
            count += _count_nodes(child, node_types)
    return count
