"""Domain value objects: SmellType, Severity, Category, Smell, Metric, ClassMetrics, FileReport, ProjectReport."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    ARCHITECTURE = "Architecture"
    DESIGN = "Design"
    IMPLEMENTATION = "Implementation"
    ML = "ML"


class Severity(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SmellType(str, Enum):
    # Architecture
    UNSTABLE_DEPENDENCY = "Unstable Dependency"
    GOD_COMPONENT = "God Component"
    FEATURE_CONCENTRATION = "Feature Concentration"
    DENSE_STRUCTURE = "Dense Structure"
    # Design
    MULTIFACETED_ABSTRACTION = "Multifaceted Abstraction"
    FEATURE_ENVY = "Feature Envy"
    DEFICIENT_ENCAPSULATION = "Deficient Encapsulation"
    INSUFFICIENT_MODULARIZATION = "Insufficient Modularization"
    BROKEN_MODULARIZATION = "Broken Modularization"
    HUB_LIKE_MODULARIZATION = "Hub-like Modularization"
    WIDE_HIERARCHY = "Wide Hierarchy"
    DEEP_HIERARCHY = "Deep Hierarchy"
    REBELLIOUS_HIERARCHY = "Rebellious Hierarchy"
    BROKEN_HIERARCHY = "Broken Hierarchy"
    # Implementation
    COMPLEX_CONDITIONAL = "Complex Conditional"
    COMPLEX_METHOD = "Complex Method"
    EMPTY_CATCH_CLAUSE = "Empty Catch Clause"
    LONG_IDENTIFIER = "Long Identifier"
    LONG_METHOD = "Long Method"
    LONG_PARAMETER_LIST = "Long Parameter List"
    LONG_STATEMENT = "Long Statement"
    MAGIC_NUMBER = "Magic Number"
    MISSING_DEFAULT = "Missing Default"
    LONG_LAMBDA_FUNCTION = "Long Lambda Function"
    LONG_MESSAGE_CHAIN = "Long Message Chain"
    # ML
    AMBIGUOUS_MERGE_KEY = "Ambiguous Merge Key"
    BROKEN_NAN_CHECK = "Broken NaN Check"
    CHAIN_INDEXING = "Chain Indexing"
    FORWARD_BYPASS = "Forward Bypass"
    TYPE_BLIND_CONVERSION = "Type Blind Conversion"
    UNNECESSARY_ITERATION = "Unnecessary Iteration"


_SMELL_META: dict[SmellType, tuple[Category, Severity]] = {
    SmellType.UNSTABLE_DEPENDENCY: (Category.ARCHITECTURE, Severity.HIGH),
    SmellType.GOD_COMPONENT: (Category.ARCHITECTURE, Severity.HIGH),
    SmellType.FEATURE_CONCENTRATION: (Category.ARCHITECTURE, Severity.MEDIUM),
    SmellType.DENSE_STRUCTURE: (Category.ARCHITECTURE, Severity.HIGH),
    SmellType.MULTIFACETED_ABSTRACTION: (Category.DESIGN, Severity.MEDIUM),
    SmellType.FEATURE_ENVY: (Category.DESIGN, Severity.MEDIUM),
    SmellType.DEFICIENT_ENCAPSULATION: (Category.DESIGN, Severity.MEDIUM),
    SmellType.INSUFFICIENT_MODULARIZATION: (Category.DESIGN, Severity.MEDIUM),
    SmellType.BROKEN_MODULARIZATION: (Category.DESIGN, Severity.HIGH),
    SmellType.HUB_LIKE_MODULARIZATION: (Category.DESIGN, Severity.HIGH),
    SmellType.WIDE_HIERARCHY: (Category.DESIGN, Severity.MEDIUM),
    SmellType.DEEP_HIERARCHY: (Category.DESIGN, Severity.MEDIUM),
    SmellType.REBELLIOUS_HIERARCHY: (Category.DESIGN, Severity.MEDIUM),
    SmellType.BROKEN_HIERARCHY: (Category.DESIGN, Severity.HIGH),
    SmellType.COMPLEX_CONDITIONAL: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.COMPLEX_METHOD: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.EMPTY_CATCH_CLAUSE: (Category.IMPLEMENTATION, Severity.HIGH),
    SmellType.LONG_IDENTIFIER: (Category.IMPLEMENTATION, Severity.LOW),
    SmellType.LONG_METHOD: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.LONG_PARAMETER_LIST: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.LONG_STATEMENT: (Category.IMPLEMENTATION, Severity.LOW),
    SmellType.MAGIC_NUMBER: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.MISSING_DEFAULT: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.LONG_LAMBDA_FUNCTION: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.LONG_MESSAGE_CHAIN: (Category.IMPLEMENTATION, Severity.MEDIUM),
    SmellType.AMBIGUOUS_MERGE_KEY: (Category.ML, Severity.HIGH),
    SmellType.BROKEN_NAN_CHECK: (Category.ML, Severity.HIGH),
    SmellType.CHAIN_INDEXING: (Category.ML, Severity.HIGH),
    SmellType.FORWARD_BYPASS: (Category.ML, Severity.MEDIUM),
    SmellType.TYPE_BLIND_CONVERSION: (Category.ML, Severity.MEDIUM),
    SmellType.UNNECESSARY_ITERATION: (Category.ML, Severity.MEDIUM),
}


@dataclass(frozen=True)
class Smell:
    smell_type: SmellType
    category: Category
    severity: Severity
    file_path: str
    line: int
    element: str
    message: str

    @classmethod
    def create(
        cls,
        smell_type: SmellType,
        file_path: str,
        line: int,
        element: str,
        message: str,
    ) -> Smell:
        cat, sev = _SMELL_META[smell_type]
        return cls(
            smell_type=smell_type,
            category=cat,
            severity=sev,
            file_path=file_path,
            line=line,
            element=element,
            message=message,
        )


@dataclass(frozen=True)
class Metric:
    name: str
    value: int | float
    file_path: str
    element: str


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


@dataclass
class FileReport:
    file_path: str
    smells: list[Smell] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    analysis: AnalysisData | None = None


@dataclass
class ProjectReport:
    files: list[FileReport] = field(default_factory=list)

    @property
    def total_smells(self) -> int:
        return sum(len(f.smells) for f in self.files)

    @property
    def total_metrics(self) -> int:
        return sum(len(f.metrics) for f in self.files)

    def smells_by_category(self) -> dict[Category, list[Smell]]:
        result: dict[Category, list[Smell]] = {c: [] for c in Category}
        for f in self.files:
            for s in f.smells:
                result[s.category].append(s)
        return result

    def smells_by_severity(self) -> dict[Severity, list[Smell]]:
        result: dict[Severity, list[Smell]] = {s: [] for s in Severity}
        for f in self.files:
            for s in f.smells:
                result[s.severity].append(s)
        return result
