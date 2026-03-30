"""Output formatters: text (terminal) and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from quali2.domain.models import Category, ProjectReport, Severity


def format_text(report: ProjectReport) -> str:
    lines: list[str] = []

    for fr in report.files:
        lines.append(f"\n{'=' * 72}")
        lines.append(f"  {fr.file_path}")
        lines.append(f"{'=' * 72}")

        # Smells
        if fr.smells:
            lines.append(f"\n  Smells ({len(fr.smells)}):")
            for s in sorted(fr.smells, key=lambda x: (x.category.value, x.line)):
                sev_icon = {"High": "!!", "Medium": "! ", "Low": "i "}
                lines.append(
                    f"    [{sev_icon.get(s.severity.value, '  ')}] "
                    f"L{s.line:>4}  [{s.category.value}] {s.smell_type.value}"
                )
                lines.append(f"          {s.element}: {s.message}")
        else:
            lines.append("\n  Smells: none")

        # Metrics summary
        if fr.metrics:
            lines.append(f"\n  Metrics:")
            for m in fr.metrics:
                lines.append(f"    {m.element:40s}  {m.name:6s} = {m.value}")

    # Summary
    lines.append(f"\n{'=' * 72}")
    lines.append(f"  Summary")
    lines.append(f"{'=' * 72}")
    lines.append(f"  Files analyzed : {len(report.files)}")
    lines.append(f"  Total smells   : {report.total_smells}")
    lines.append(f"  Total metrics  : {report.total_metrics}")

    by_sev = report.smells_by_severity()
    for sev in Severity:
        count = len(by_sev[sev])
        if count:
            lines.append(f"    {sev.value:8s}: {count}")

    by_cat = report.smells_by_category()
    for cat in Category:
        count = len(by_cat[cat])
        if count:
            lines.append(f"    {cat.value:14s}: {count}")

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
