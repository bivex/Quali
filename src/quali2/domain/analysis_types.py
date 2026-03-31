"""Analysis-specific data structures for code extraction."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParamInfo:
    name: str


@dataclass
class MethodInfo:
    name: str
    line_start: int
    line_end: int
    params: list[ParamInfo] = field(default_factory=list)
    cyclomatic_complexity: int = 1
    num_statements: int = 0
    accesses_attrs: set[str] = field(default_factory=set)
    is_property: bool = False


@dataclass
class ClassInfo:
    name: str
    line_start: int
    line_end: int
    bases: list[str] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    fields: set[str] = field(default_factory=set)
    decorators: list[str] = field(default_factory=list)
    depth_inheritance: int = 0


@dataclass
class ImportInfo:
    module: str
    names: list[str] = field(default_factory=list)
    alias: str | None = None
    line: int = 0


@dataclass
class AnalysisData:
    file_path: str
    imports: list[ImportInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    top_level_functions: list[MethodInfo] = field(default_factory=list)
    total_lines: int = 0
