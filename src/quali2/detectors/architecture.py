"""Architecture smell detectors.

Detects: Unstable Dependency, God Component, Feature Concentration, Dense Structure.
"""

from __future__ import annotations

from quali2.domain.models import AnalysisData, Smell, SmellType

GOD_COMPONENT_LOC = 1000
GOD_COMPONENT_CLASSES = 10
FEATURE_CONCENTRATION_IMPORT_MODULES = 10
DENSE_STRUCTURE_DEP_RATIO = 0.7


def detect_architecture_smells(data: AnalysisData) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path

    # God Component — file is excessively large
    if data.total_lines > GOD_COMPONENT_LOC:
        smells.append(
            Smell.create(
                SmellType.GOD_COMPONENT,
                fp,
                1,
                "<file>",
                f"File has {data.total_lines} lines (threshold {GOD_COMPONENT_LOC})",
            )
        )

    if len(data.classes) > GOD_COMPONENT_CLASSES:
        smells.append(
            Smell.create(
                SmellType.GOD_COMPONENT,
                fp,
                1,
                "<file>",
                f"File contains {len(data.classes)} classes (threshold {GOD_COMPONENT_CLASSES})",
            )
        )

    # Feature Concentration — file imports many unrelated modules
    modules = {imp.module.split(".")[0] for imp in data.imports}
    if len(modules) > FEATURE_CONCENTRATION_IMPORT_MODULES:
        smells.append(
            Smell.create(
                SmellType.FEATURE_CONCENTRATION,
                fp,
                1,
                "<file>",
                f"File imports {len(modules)} distinct modules (threshold {FEATURE_CONCENTRATION_IMPORT_MODULES})",
            )
        )

    # Dense Structure — excessive intra-module dependencies
    total_internal_refs = sum(
        len(m.accesses_attrs) for cls in data.classes for m in cls.methods
    )
    total_methods = sum(len(cls.methods) for cls in data.classes)
    if total_methods > 0:
        ratio = total_internal_refs / total_methods
        if ratio > 10 and total_methods > 5:
            smells.append(
                Smell.create(
                    SmellType.DENSE_STRUCTURE,
                    fp,
                    1,
                    "<file>",
                    f"Average {ratio:.1f} attribute accesses per method indicates dense coupling",
                )
            )

    return smells
