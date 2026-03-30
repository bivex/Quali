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


def detect_design_smells(data: AnalysisData, source: str = "") -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path

    for cls in data.classes:
        elem = f"class {cls.name}"

        # Multifaceted Abstraction — too many methods in one class
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

        # Deficient Encapsulation — too many public fields
        public_fields = [f for f in cls.fields if not f.startswith("_")]
        if len(public_fields) > 5:
            smells.append(
                Smell.create(
                    SmellType.DEFICIENT_ENCAPSULATION,
                    fp,
                    cls.line_start,
                    elem,
                    f"Class exposes {len(public_fields)} public instance attributes",
                )
            )

        # Feature Envy — methods accessing more external attrs than own
        for m in cls.methods:
            own_attrs = {f for f in cls.fields}
            own_accesses = m.accesses_attrs & own_attrs
            if (
                len(m.accesses_attrs) > 3
                and len(own_accesses) < len(m.accesses_attrs) * 0.3
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

        # Insufficient Modularization — class is too large
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

        # Hub-like Modularization — class depends on too many others
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

        # Deep Hierarchy
        if cls.depth_inheritance >= DEEP_HIERARCHY_DEPTH:
            smells.append(
                Smell.create(
                    SmellType.DEEP_HIERARCHY,
                    fp,
                    cls.line_start,
                    elem,
                    f"Inheritance depth is {cls.depth_inheritance} (threshold {DEEP_HIERARCHY_DEPTH})",
                )
            )

    # Wide Hierarchy — many children inheriting from the same base
    base_counts: dict[str, int] = {}
    for cls in data.classes:
        for b in cls.bases:
            base_counts[b] = base_counts.get(b, 0) + 1
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

    # Rebellious Hierarchy — subclass overrides almost everything
    for cls in data.classes:
        if cls.bases and cls.methods:
            overridden = sum(1 for m in cls.methods if not m.name.startswith("__"))
            if overridden > 5 and len(cls.fields) < 2:
                smells.append(
                    Smell.create(
                        SmellType.REBELLIOUS_HIERARCHY,
                        fp,
                        cls.line_start,
                        f"class {cls.name}",
                        f"Subclass overrides {overridden} methods but defines few fields — may not extend properly",
                    )
                )

    # Broken Hierarchy — subclass does not call super().__init__
    source_lines = source.splitlines() if source else []
    for cls in data.classes:
        if cls.bases and cls.bases != ["object"]:
            has_init = any(m.name == "__init__" for m in cls.methods)
            if has_init and cls.depth_inheritance > 0:
                init_method = next(m for m in cls.methods if m.name == "__init__")
                method_src = _extract_method_source(
                    source_lines, init_method.line_start, init_method.line_end
                )
                calls_super = "super()" in method_src
                if not calls_super:
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
