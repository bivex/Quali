"""Architecture smell detectors.

Detects: Unstable Dependency, God Component, Feature Concentration, Dense Structure.

Unstable Dependency and Broken Modularization require cross-file context
and are invoked separately via detect_cross_file_smells().
"""

from __future__ import annotations

import os
from collections import defaultdict

from quali2.domain.models import AnalysisData, Smell, SmellType

GOD_COMPONENT_LOC = 1000
GOD_COMPONENT_CLASSES = 10
FEATURE_CONCENTRATION_IMPORT_MODULES = 10
DENSE_STRUCTURE_DEP_RATIO = 0.7
UNSTABLE_DEPENDENCY_THRESHOLD = 0.6
BROKEN_MODULARIZATION_SHARED_IMPORTS = 6


# ---------------------------------------------------------------------------
# Per-file detectors (run on single file)
# ---------------------------------------------------------------------------


def detect_architecture_smells(
    data: AnalysisData,
    all_data: list[AnalysisData] | None = None,
) -> list[Smell]:
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

    # Unstable Dependency (needs cross-file context)
    if all_data is not None:
        smells.extend(_detect_unstable_dependency(data, all_data))

    return smells


# ---------------------------------------------------------------------------
# Cross-file detectors
# ---------------------------------------------------------------------------


def detect_cross_file_smells(all_data: list[AnalysisData]) -> list[Smell]:
    """Run detectors that require project-wide analysis.

    Returns smells for Unstable Dependency and Broken Modularization.
    """
    smells: list[Smell] = []

    for data in all_data:
        smells.extend(_detect_unstable_dependency(data, all_data))

    smells.extend(_detect_broken_modularization(all_data))

    return smells


# ---------------------------------------------------------------------------
# Unstable Dependency
# ---------------------------------------------------------------------------


def _detect_unstable_dependency(
    data: AnalysisData, all_data: list[AnalysisData]
) -> list[Smell]:
    """Detect when a file depends on modules that are highly unstable.

    Instability I = fan_out / (fan_in + fan_out).
    I=0 → maximally stable, I=1 → maximally unstable.

    A smell fires when the file's *dependencies* have I > threshold,
    meaning the file leans on unstable foundations.
    """
    smells: list[Smell] = []
    fp = data.file_path

    # Build module → file mapping
    file_modules: dict[str, AnalysisData] = {}
    for d in all_data:
        mod = _file_to_module(d.file_path)
        file_modules[mod] = d

    # Build dependency graph
    dep_graph = _build_dependency_graph(all_data, file_modules)

    # Compute instability for each module
    instability: dict[str, float] = {}
    for mod, deps in dep_graph.items():
        fan_out = len(deps)
        fan_in = sum(1 for m, ds in dep_graph.items() if mod in ds)
        total = fan_in + fan_out
        instability[mod] = fan_out / total if total > 0 else 0.0

    my_mod = _file_to_module(fp)
    my_deps = dep_graph.get(my_mod, set())

    # Check if any dependency is unstable
    unstable_deps = [
        d for d in my_deps if instability.get(d, 0.0) > UNSTABLE_DEPENDENCY_THRESHOLD
    ]
    if unstable_deps:
        dep_list = ", ".join(sorted(unstable_deps))
        smells.append(
            Smell.create(
                SmellType.UNSTABLE_DEPENDENCY,
                fp,
                1,
                "<file>",
                f"Depends on unstable modules (I>{UNSTABLE_DEPENDENCY_THRESHOLD}): {dep_list}",
            )
        )

    return smells


# ---------------------------------------------------------------------------
# Broken Modularization
# ---------------------------------------------------------------------------


def _detect_broken_modularization(all_data: list[AnalysisData]) -> list[Smell]:
    """Detect when related responsibilities are scattered across files.

    Heuristic: two files that import the same local modules and define
    related classes/functions share a concern that should be co-located.
    """
    smells: list[Smell] = []

    if len(all_data) < 2:
        return smells

    # Build module → file mapping
    file_modules: dict[str, AnalysisData] = {}
    for d in all_data:
        mod = _file_to_module(d.file_path)
        file_modules[mod] = d

    # For each file, collect the set of imported *local* modules
    local_imports: dict[str, set[str]] = {}
    for d in all_data:
        mod = _file_to_module(d.file_path)
        local_imports[mod] = {
            _normalize_import(imp.module)
            for imp in d.imports
            if _is_local_import(imp.module, file_modules)
        }

    # For each pair of files, check if they share many local imports
    modules = list(local_imports.keys())
    for i in range(len(modules)):
        for j in range(i + 1, len(modules)):
            ma, mb = modules[i], modules[j]
            shared = local_imports[ma] & local_imports[mb]
            if len(shared) >= BROKEN_MODULARIZATION_SHARED_IMPORTS:
                # Both files depend on the same local modules → potential split
                shared_list = ", ".join(sorted(shared))
                # Report on the smaller file (less cohesive)
                data_a = file_modules[ma]
                data_b = file_modules[mb]
                target = data_a if data_a.total_lines <= data_b.total_lines else data_b
                smells.append(
                    Smell.create(
                        SmellType.BROKEN_MODULARIZATION,
                        target.file_path,
                        1,
                        "<file>",
                        f"Shares {len(shared)} local imports with {_file_to_module(data_b.file_path if target is data_a else data_a.file_path)}: {shared_list}",
                    )
                )

    return smells


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_to_module(file_path: str) -> str:
    """Convert a file path to a dotted module name."""
    base = os.path.splitext(os.path.basename(file_path))[0]
    return base


def _normalize_import(module: str) -> str:
    """Get the top-level module name from an import path."""
    return module.split(".")[0]


def _is_local_import(module: str, file_modules: dict[str, AnalysisData]) -> bool:
    """Check if an import refers to another file in the project."""
    top = _normalize_import(module)
    return top in file_modules


def _build_dependency_graph(
    all_data: list[AnalysisData],
    file_modules: dict[str, AnalysisData],
) -> dict[str, set[str]]:
    """Build a module → set-of-imported-local-modules graph."""
    graph: dict[str, set[str]] = {}
    for d in all_data:
        mod = _file_to_module(d.file_path)
        deps = set()
        for imp in d.imports:
            top = _normalize_import(imp.module)
            if top in file_modules and top != mod:
                deps.add(top)
        graph[mod] = deps
    return graph
