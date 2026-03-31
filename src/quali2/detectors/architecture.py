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
DENSE_STRUCTURE_AVG_ACCESSES = 10
UNSTABLE_DEPENDENCY_THRESHOLD = 0.4
BROKEN_MODULARIZATION_SHARED_IMPORTS = 6


# ---------------------------------------------------------------------------
# Per-file detectors (run on single file)
# ---------------------------------------------------------------------------


def detect_architecture_smells(
    data: AnalysisData,
    all_data: list[AnalysisData] | None = None,
) -> list[Smell]:
    smells: list[Smell] = []
    smells.extend(_detect_god_component(data))
    smells.extend(_detect_feature_concentration(data))
    smells.extend(_detect_dense_structure(data))
    if all_data is not None:
        smells.extend(_detect_unstable_dependency(data, all_data))
    return smells


def _detect_god_component(data: AnalysisData) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path
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
    return smells


def _detect_feature_concentration(data: AnalysisData) -> list[Smell]:
    fp = data.file_path
    modules = {imp.module.split(".")[0] for imp in data.imports}
    if len(modules) > FEATURE_CONCENTRATION_IMPORT_MODULES:
        return [
            Smell.create(
                SmellType.FEATURE_CONCENTRATION,
                fp,
                1,
                "<file>",
                f"File imports {len(modules)} distinct modules (threshold {FEATURE_CONCENTRATION_IMPORT_MODULES})",
            )
        ]
    return []


def _detect_dense_structure(data: AnalysisData) -> list[Smell]:
    fp = data.file_path
    total_refs = sum(len(m.accesses_attrs) for cls in data.classes for m in cls.methods)
    total_methods = sum(len(cls.methods) for cls in data.classes)
    if total_methods > 0:
        ratio = total_refs / total_methods
        if ratio > DENSE_STRUCTURE_AVG_ACCESSES and total_methods > 5:
            return [
                Smell.create(
                    SmellType.DENSE_STRUCTURE,
                    fp,
                    1,
                    "<file>",
                    f"Average {ratio:.1f} attribute accesses per method indicates dense coupling",
                )
            ]
    return []


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


def _compute_instability(dep_graph: dict[str, set[str]]) -> dict[str, float]:
    instability: dict[str, float] = {}
    for mod, deps in dep_graph.items():
        fan_out = len(deps)
        fan_in = sum(1 for m, ds in dep_graph.items() if mod in ds)
        total = fan_in + fan_out
        instability[mod] = fan_out / total if total > 0 else 0.0
    return instability


def _detect_unstable_dependency(
    data: AnalysisData, all_data: list[AnalysisData]
) -> list[Smell]:
    fp = data.file_path

    file_modules: dict[str, AnalysisData] = {}
    for d in all_data:
        file_modules[_file_to_module(d.file_path)] = d

    dep_graph = _build_dependency_graph(all_data, file_modules)
    instability = _compute_instability(dep_graph)

    my_mod = _file_to_module(fp)
    my_deps = dep_graph.get(my_mod, set())
    unstable_deps = [
        d for d in my_deps if instability.get(d, 0.0) > UNSTABLE_DEPENDENCY_THRESHOLD
    ]
    if not unstable_deps:
        return []

    dep_list = ", ".join(sorted(unstable_deps))
    return [
        Smell.create(
            SmellType.UNSTABLE_DEPENDENCY,
            fp,
            1,
            "<file>",
            f"Depends on unstable modules (I>{UNSTABLE_DEPENDENCY_THRESHOLD}): {dep_list}",
        )
    ]


# ---------------------------------------------------------------------------
# Broken Modularization
# ---------------------------------------------------------------------------


def _detect_broken_modularization(all_data: list[AnalysisData]) -> list[Smell]:
    if len(all_data) < 2:
        return []

    file_modules: dict[str, AnalysisData] = {}
    for d in all_data:
        file_modules[_file_to_module(d.file_path)] = d

    local_imports = _collect_local_imports(all_data, file_modules)
    return _find_shared_import_smells(local_imports, file_modules)


def _find_shared_import_smells(
    local_imports: dict[str, set[str]],
    file_modules: dict[str, AnalysisData],
) -> list[Smell]:
    smells: list[Smell] = []
    modules = list(local_imports.keys())
    for i in range(len(modules)):
        for j in range(i + 1, len(modules)):
            ma, mb = modules[i], modules[j]
            shared = local_imports[ma] & local_imports[mb]
            if len(shared) >= BROKEN_MODULARIZATION_SHARED_IMPORTS:
                smells.append(
                    _make_broken_mod_smell(shared, file_modules[ma], file_modules[mb])
                )
    return smells


def _make_broken_mod_smell(
    shared: set[str], data_a: AnalysisData, data_b: AnalysisData
) -> Smell:
    shared_list = ", ".join(sorted(shared))
    target = data_a if data_a.total_lines <= data_b.total_lines else data_b
    other = data_b if target is data_a else data_a
    return Smell.create(
        SmellType.BROKEN_MODULARIZATION,
        target.file_path,
        1,
        "<file>",
        f"Shares {len(shared)} local imports with {_file_to_module(other.file_path)}: {shared_list}",
    )


def _collect_local_imports(
    all_data: list[AnalysisData],
    file_modules: dict[str, AnalysisData],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for d in all_data:
        mod = _file_to_module(d.file_path)
        result[mod] = {
            _normalize_import(imp.module)
            for imp in d.imports
            if _is_local_import(imp.module, file_modules)
        }
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_to_module(file_path: str) -> str:
    """Convert a file path to a dotted module name."""
    return os.path.splitext(os.path.basename(file_path))[0]


def _normalize_import(module: str) -> str:
    """Get the top-level module name from an import path."""
    return module.split(".")[0]


def _is_local_import(module: str, file_modules: dict[str, AnalysisData]) -> bool:
    """Check if an import refers to another file in the project."""
    return _normalize_import(module) in file_modules


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
