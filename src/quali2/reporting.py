"""Output formatters: text (terminal) and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from quali2.domain.models import (
    Category,
    Metric,
    ProjectReport,
    Severity,
    Smell,
)

_SEV_ICONS = {"High": "!!", "Medium": "! ", "Low": "i "}


def _format_smell(s: Smell) -> list[str]:
    icon = _SEV_ICONS.get(s.severity.value, "  ")
    return [
        f"    [{icon}] L{s.line:>4}  [{s.category.value}] {s.smell_type.value}",
        f"          {s.element}: {s.message}",
    ]


def _sort_smells(smells: list[Smell]) -> list[Smell]:
    return sorted(smells, key=lambda x: (x.category.value, x.line))


def _format_file_section(fr) -> list[str]:
    lines = [
        f"\n{'=' * 72}",
        f"  {fr.file_path}",
        f"{'=' * 72}",
    ]
    if fr.smells:
        lines.append(f"\n  Smells ({len(fr.smells)}):")
        for s in _sort_smells(fr.smells):
            lines.extend(_format_smell(s))
    else:
        lines.append("\n  Smells: none")
    if fr.metrics:
        lines.append("\n  Metrics:")
        for m in fr.metrics:
            lines.append(f"    {m.element:40s}  {m.name:6s} = {m.value}")
    return lines


def _format_summary(report: ProjectReport) -> list[str]:
    lines = [
        f"\n{'=' * 72}",
        "  Summary",
        f"{'=' * 72}",
        f"  Files analyzed : {len(report.files)}",
        f"  Total smells   : {report.total_smells}",
        f"  Total metrics  : {report.total_metrics}",
    ]
    for sev in Severity:
        count = len(report.smells_by_severity()[sev])
        if count:
            lines.append(f"    {sev.value:8s}: {count}")
    for cat in Category:
        count = len(report.smells_by_category()[cat])
        if count:
            lines.append(f"    {cat.value:14s}: {count}")
    return lines


def format_text(report: ProjectReport) -> str:
    lines: list[str] = []
    for fr in report.files:
        lines.extend(_format_file_section(fr))
    lines.extend(_format_summary(report))
    return "\n".join(lines)


def format_json(report: ProjectReport) -> str:
    data = {
        "files": [],
        "summary": {
            "files_analyzed": len(report.files),
            "total_smells": report.total_smells,
            "total_metrics": report.total_metrics,
        },
    }
    for fr in report.files:
        file_data = {
            "file_path": fr.file_path,
            "smells": [asdict(s) for s in fr.smells],
            "metrics": [asdict(m) for m in fr.metrics],
        }
        data["files"].append(file_data)

    return json.dumps(data, indent=2, default=str)
