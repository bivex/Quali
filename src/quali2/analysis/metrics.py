"""OO metrics computation over AnalysisData."""

from __future__ import annotations

from quali2.domain.models import AnalysisData, ClassInfo, Metric, MethodInfo


def compute_metrics(data: AnalysisData) -> list[Metric]:
    metrics: list[Metric] = []
    fp = data.file_path

    # File-level
    metrics.append(Metric("LOC", data.total_lines, fp, "<file>"))

    # Module fan-in / fan-out
    imported = {imp.module.split(".")[0] for imp in data.imports}
    metrics.append(Metric("FANOUT", len(imported), fp, "<module>"))

    # Per-class metrics
    for cls in data.classes:
        elem = f"class {cls.name}"
        metrics.append(Metric("NOF", len(cls.fields), fp, elem))
        nopf = sum(1 for f in cls.fields if not f.startswith("_"))
        metrics.append(Metric("NOPF", nopf, fp, elem))
        metrics.append(Metric("NOM", len(cls.methods), fp, elem))
        nopm = sum(1 for m in cls.methods if not m.name.startswith("_"))
        metrics.append(Metric("NOPM", nopm, fp, elem))
        wmc = sum(m.cyclomatic_complexity for m in cls.methods)
        metrics.append(Metric("WMC", wmc, fp, elem))
        metrics.append(Metric("DIT", cls.depth_inheritance, fp, elem))
        lcom = _lcom(cls)
        metrics.append(Metric("LCOM", lcom, fp, elem))

    # Per-method metrics
    for fn in data.top_level_functions:
        elem = f"function {fn.name}"
        _method_metrics(metrics, fn, fp, elem)

    for cls in data.classes:
        for m in cls.methods:
            elem = f"{cls.name}.{m.name}"
            _method_metrics(metrics, m, fp, elem)

    return metrics


def _method_metrics(metrics: list[Metric], m: MethodInfo, fp: str, elem: str) -> None:
    metrics.append(Metric("LOC", m.num_statements, fp, elem))
    metrics.append(Metric("CC", m.cyclomatic_complexity, fp, elem))
    metrics.append(Metric("PC", len(m.params), fp, elem))


def _lcom(cls: ClassInfo) -> float:
    """LCOM* (Lack of Cohesion of Methods).

    Pairs of methods that share no instance-field access vs pairs that do.
    Returns a float in [0, 1]. Higher = less cohesive.
    """
    methods = [m for m in cls.methods if not m.name.startswith("__")]
    if len(methods) < 2 or not cls.fields:
        return 0.0

    n = len(methods)
    p = 0  # pairs sharing no field
    q = 0  # pairs sharing at least one field

    for i in range(n):
        for j in range(i + 1, n):
            shared = methods[i].accesses_attrs & methods[j].accesses_attrs
            if shared:
                q += 1
            else:
                p += 1

    total = p + q
    if total == 0:
        return 0.0
    return max(0.0, (p - q) / total)
