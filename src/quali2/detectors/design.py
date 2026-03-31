"""Design smell detectors.

Detects: Multifaceted Abstraction, Feature Envy, Deficient Encapsulation,
Insufficient Modularization, Broken Modularization, Hub-like Modularization,
Wide Hierarchy, Deep Hierarchy, Rebellious Hierarchy, Broken Hierarchy.
"""

from __future__ import annotations

from quali2.domain.models import AnalysisData, Smell, SmellType

MULTIFACETED_METHODS = 15
INSUFFICIENT_LOC = 500
HUB_LIKE_FAN = 15
WIDE_HIERARCHY_CHILDREN = 10
DEEP_HIERARCHY_DEPTH = 5
FEATURE_ENVY_OWN_RATIO = 0.3


def detect_design_smells(data: AnalysisData, source: str = "") -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path

    for cls in data.classes:
        elem = f"class {cls.name}"
        smells.extend(_check_class_smells(fp, cls))

    smells.extend(_check_wide_hierarchy(fp, data.classes))
    smells.extend(_check_rebellious_hierarchy(fp, data.classes))

    source_lines = source.splitlines() if source else []
    smells.extend(_check_broken_hierarchy(fp, data.classes, source_lines))

    return smells


def _check_class_smells(fp: str, cls) -> list[Smell]:
    smells: list[Smell] = []
    elem = f"class {cls.name}"
    smells.extend(_check_class_size(fp, cls, elem))
    smells.extend(_check_class_encapsulation(fp, cls, elem))
    smells.extend(_check_feature_envy(fp, cls))
    return smells


def _check_class_size(fp: str, cls, elem: str) -> list[Smell]:
    smells: list[Smell] = []
    smells.extend(_check_size_and_hubs(fp, cls, elem))
    smells.extend(_check_inheritance(fp, cls, elem))
    return smells


def _check_size_and_hubs(fp: str, cls, elem: str) -> list[Smell]:
    smells: list[Smell] = []
    if len(cls.methods) > MULTIFACETED_METHODS:
        smells.append(
            Smell.create(
                SmellType.MULTIFACETED_ABSTRACTION,
                fp,
                cls.line_start,
                elem,
                f"Class has {len(cls.methods)} methods (threshold {MULTIFACETED_METHODS})",
            )
        )
    class_loc = cls.line_end - cls.line_start + 1
    if class_loc > INSUFFICIENT_LOC:
        smells.append(
            Smell.create(
                SmellType.INSUFFICIENT_MODULARIZATION,
                fp,
                cls.line_start,
                elem,
                f"Class spans {class_loc} lines (threshold {INSUFFICIENT_LOC})",
            )
        )
    if len(cls.bases) > HUB_LIKE_FAN:
        smells.append(
            Smell.create(
                SmellType.HUB_LIKE_MODULARIZATION,
                fp,
                cls.line_start,
                elem,
                f"Class has {len(cls.bases)} base classes (threshold {HUB_LIKE_FAN})",
            )
        )
    return smells


def _check_inheritance(fp: str, cls, elem: str) -> list[Smell]:
    if cls.depth_inheritance >= DEEP_HIERARCHY_DEPTH:
        return [
            Smell.create(
                SmellType.DEEP_HIERARCHY,
                fp,
                cls.line_start,
                elem,
                f"Inheritance depth is {cls.depth_inheritance} (threshold {DEEP_HIERARCHY_DEPTH})",
            )
        ]
    return []


def _check_class_encapsulation(fp: str, cls, elem: str) -> list[Smell]:
    public_fields = [f for f in cls.fields if not f.startswith("_")]
    if len(public_fields) > 5:
        return [
            Smell.create(
                SmellType.DEFICIENT_ENCAPSULATION,
                fp,
                cls.line_start,
                elem,
                f"Class exposes {len(public_fields)} public instance attributes",
            )
        ]
    return []


def _check_feature_envy(fp: str, cls) -> list[Smell]:
    smells: list[Smell] = []
    own_attrs = cls.fields
    for m in cls.methods:
        own_accesses = m.accesses_attrs & own_attrs
        if (
            len(m.accesses_attrs) > 3
            and len(own_accesses) < len(m.accesses_attrs) * FEATURE_ENVY_OWN_RATIO
        ):
            smells.append(
                Smell.create(
                    SmellType.FEATURE_ENVY,
                    fp,
                    m.line_start,
                    f"{cls.name}.{m.name}",
                    f"Method accesses {len(m.accesses_attrs)} attributes but only {len(own_accesses)} belong to its class",
                )
            )
    return smells


def _check_wide_hierarchy(fp: str, classes) -> list[Smell]:
    base_counts: dict[str, int] = {}
    for cls in classes:
        for b in cls.bases:
            base_counts[b] = base_counts.get(b, 0) + 1
    smells: list[Smell] = []
    for base, count in base_counts.items():
        if count >= WIDE_HIERARCHY_CHILDREN:
            smells.append(
                Smell.create(
                    SmellType.WIDE_HIERARCHY,
                    fp,
                    1,
                    f"<base: {base}>",
                    f"Base class '{base}' has {count} subclasses (threshold {WIDE_HIERARCHY_CHILDREN})",
                )
            )
    return smells


def _check_rebellious_hierarchy(fp: str, classes) -> list[Smell]:
    smells: list[Smell] = []
    for cls in classes:
        if cls.bases and cls.methods:
            overridden = sum(1 for m in cls.methods if not m.name.startswith("__"))
            if overridden > 5 and len(cls.fields) < 2:
                smells.append(
                    Smell.create(
                        SmellType.REBELLIOUS_HIERARCHY,
                        fp,
                        cls.line_start,
                        f"class {cls.name}",
                        "Subclass overrides {0} methods but defines few fields — may not extend properly".format(
                            overridden
                        ),
                    )
                )
    return smells


def _check_broken_hierarchy(fp: str, classes, source_lines: list[str]) -> list[Smell]:
    smells: list[Smell] = []
    for cls in classes:
        if cls.bases and cls.bases != ["object"]:
            has_init = any(m.name == "__init__" for m in cls.methods)
            if has_init and cls.depth_inheritance > 0:
                init_method = next(m for m in cls.methods if m.name == "__init__")
                method_src = _extract_method_source(
                    source_lines, init_method.line_start, init_method.line_end
                )
                if "super()" not in method_src:
                    smells.append(
                        Smell.create(
                            SmellType.BROKEN_HIERARCHY,
                            fp,
                            cls.line_start,
                            f"class {cls.name}",
                            "Subclass defines __init__ but does not call super().__init__()",
                        )
                    )
    return smells


def _extract_method_source(source_lines: list[str], start: int, end: int) -> str:
    """Extract source lines for a method (1-indexed line numbers)."""
    if not source_lines or start < 1:
        return ""
    return "\n".join(source_lines[start - 1 : end])
