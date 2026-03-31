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

    def __init__(self, file_path: str, source_lines: list[str]) -> None:
        self.data = AnalysisData(file_path=file_path, total_lines=len(source_lines))
        self._source_lines = source_lines
        self._class_stack: list[ClassInfo] = []
        self._method_stack: list[MethodInfo] = []
        self._class_map: dict[str, ClassInfo] = {}
        self._current_class_idx: int | None = None

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------

    def visitFile_input(self, ctx: Python3Parser.File_inputContext):
        self.visitChildren(ctx)
        return self.data

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------

    def visitImport_name(self, ctx: Python3Parser.Import_nameContext):
        dotted = ctx.dotted_as_names()
        if dotted:
            for dan in dotted.dotted_as_name():
                mod = self._text(dan.dotted_name())
                alias = self._text(dan.name()) if dan.name() else None
                self.data.imports.append(
                    ImportInfo(module=mod, alias=alias, line=ctx.start.line)
                )
        self.visitChildren(ctx)

    def visitImport_from(self, ctx: Python3Parser.Import_fromContext):
        mod = self._text(ctx.dotted_name()) if ctx.dotted_name() else ""
        names: list[str] = []
        if ctx.import_as_names():
            for ian in ctx.import_as_names().import_as_name():
                names.append(self._text(ian.name(0)))
        elif ctx.STAR():
            names = ["*"]
        self.data.imports.append(
            ImportInfo(module=mod, names=names, line=ctx.start.line)
        )
        self.visitChildren(ctx)

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------

    def visitFuncdef(self, ctx: Python3Parser.FuncdefContext):
        name = self._text(ctx.name())
        line_start = ctx.start.line
        line_end = ctx.stop.line
        params_ctx = ctx.parameters().typedargslist() if ctx.parameters() else None
        params = self._extract_params(params_ctx)
        cc = self._calc_cyclomatic(ctx)

        mi = MethodInfo(
            name=name,
            line_start=line_start,
            line_end=line_end,
            params=[ParamInfo(name=p) for p in params],
            cyclomatic_complexity=cc,
            num_statements=line_end - line_start + 1,
        )

        if self._class_stack:
            cls = self._class_stack[-1]
            cls.methods.append(mi)
            if name == "__init__":
                self._extract_self_attrs(ctx, cls)
        else:
            self.data.top_level_functions.append(mi)

        self._method_stack.append(mi)
        self.visitChildren(ctx)
        self._method_stack.pop()

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    def visitClassdef(self, ctx: Python3Parser.ClassdefContext):
        name = self._text(ctx.name())
        line_start = ctx.start.line
        line_end = ctx.stop.line

        bases: list[str] = []
        if ctx.arglist():
            for arg in ctx.arglist().argument():
                tests = arg.test()
                if tests:
                    first_test = tests[0] if isinstance(tests, list) else tests
                    bases.append(self._text(first_test))

        decorators: list[str] = []
        parent = ctx.parentCtx
        if isinstance(parent, Python3Parser.DecoratedContext):
            for dec in parent.decorators().decorator():
                decorators.append(self._text(dec.dotted_name()))

        depth = self._inheritance_depth(bases)
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
        self.visitChildren(ctx)
        self._class_stack.pop()

    # ------------------------------------------------------------------
    # Try / Except
    # ------------------------------------------------------------------

    def visitTry_stmt(self, ctx: Python3Parser.Try_stmtContext):
        self.visitChildren(ctx)

    # ------------------------------------------------------------------
    # Attribute access tracking (for LCOM & feature envy)
    # ------------------------------------------------------------------

    def visitExpr_stmt(self, ctx: Python3Parser.Expr_stmtContext):
        self._collect_attr_accesses(ctx)
        self.visitChildren(ctx)

    def visitAtom_expr(self, ctx: Python3Parser.Atom_exprContext):
        self._collect_attr_accesses(ctx)
        self.visitChildren(ctx)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_params(self, tal_ctx) -> list[str]:
        if tal_ctx is None:
            return []
        params: list[str] = []
        for t in tal_ctx.tfpdef():
            params.append(self._text(t.name()))
        return params

    def _extract_self_attrs(self, func_ctx, cls: ClassInfo) -> None:
        attr_refs = self._find_self_attr_refs(func_ctx)
        for attr_name in attr_refs:
            cls.fields.add(attr_name)

    def _collect_attr_accesses(self, ctx: ParserRuleContext) -> None:
        if not self._method_stack:
            return
        text = self._text(ctx)
        if ".self" in text or text.startswith("self."):
            parts = text.split(".")
            if len(parts) > 1 and parts[0] == "self":
                attr = parts[1].split("(")[0].split("[")[0]
                self._method_stack[-1].accesses_attrs.add(attr)

    def _find_self_attr_refs(self, ctx: ParserRuleContext) -> set[str]:
        refs: list[str] = []
        self._collect_self_refs(ctx, refs)
        return set(refs)

    def _collect_self_refs(self, ctx: ParserRuleContext, refs: list[str]) -> None:
        text = self._text(ctx)
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
                self._collect_self_refs(child, refs)

    def _inheritance_depth(self, bases: list[str]) -> int:
        if not bases or bases == ["object"]:
            return 0
        max_depth = 0
        for b in bases:
            if b in self._class_map:
                max_depth = max(max_depth, self._class_map[b].depth_inheritance + 1)
            else:
                max_depth = max(max_depth, 1)
        return max_depth

    def _calc_cyclomatic(self, ctx: ParserRuleContext) -> int:
        complexity = 1
        complexity += self._count_nodes(
            ctx,
            (
                Python3Parser.If_stmtContext,
                Python3Parser.While_stmtContext,
                Python3Parser.For_stmtContext,
                Python3Parser.Except_clauseContext,
            ),
        )
        text = self._text(ctx)
        complexity += text.count(" and ") + text.count(" or ")
        return complexity

    def _count_nodes(self, ctx: ParserRuleContext, node_types: tuple) -> int:
        count = 0
        for t in node_types:
            if isinstance(ctx, t):
                count += 1
        for child in ctx.getChildren():
            if isinstance(child, ParserRuleContext):
                count += self._count_nodes(child, node_types)
        return count

    def _is_empty_block(self, block_ctx) -> bool:
        text = self._text(block_ctx).strip()
        if not text or text in ("pass", "..."):
            return True
        return False

    def _containing_element(self, ctx: ParserRuleContext) -> str:
        node = ctx.parentCtx
        while node is not None:
            if isinstance(node, Python3Parser.FuncdefContext):
                return self._text(node.name())
            if isinstance(node, Python3Parser.ClassdefContext):
                return self._text(node.name())
            node = node.parentCtx
        return "<module>"

    @staticmethod
    def _text(ctx) -> str:
        if ctx is None:
            return ""
        return ctx.getText()
