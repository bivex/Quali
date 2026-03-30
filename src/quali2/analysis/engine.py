"""Analysis engine: parses Python files via ANTLR4 and runs all detectors."""

from __future__ import annotations

import os
from pathlib import Path

from antlr4 import CommonTokenStream, InputStream

from quali2.antlr.Python3Lexer import Python3Lexer
from quali2.antlr.Python3Parser import Python3Parser
from quali2.analysis.metrics import compute_metrics
from quali2.analysis.visitor import PythonAnalysisVisitor
from quali2.domain.models import AnalysisData, FileReport, ProjectReport, Smell
from quali2.detectors.architecture import detect_architecture_smells
from quali2.detectors.design import detect_design_smells
from quali2.detectors.implementation import detect_implementation_smells
from quali2.detectors.ml import detect_ml_smells


def parse_file(file_path: str) -> tuple[AnalysisData, str]:
    """Parse a single Python file and return analysis data + source text."""
    with open(file_path, encoding="utf-8", errors="replace") as f:
        source = f.read()

    source_lines = source.splitlines()
    input_stream = InputStream(source)
    lexer = Python3Lexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = Python3Parser(token_stream)

    try:
        tree = parser.file_input()
    except Exception:
        return AnalysisData(file_path=file_path, total_lines=len(source_lines)), source

    visitor = PythonAnalysisVisitor(file_path, source_lines)
    visitor.visit(tree)
    return visitor.data, source


def analyze_file(file_path: str) -> FileReport:
    """Full analysis of one file: parse -> metrics -> smell detection."""
    data, source = parse_file(file_path)
    metrics = compute_metrics(data)

    smells: list[Smell] = []
    smells.extend(detect_architecture_smells(data))
    smells.extend(detect_design_smells(data, source))
    smells.extend(detect_implementation_smells(data, source))
    smells.extend(detect_ml_smells(data, source))

    return FileReport(
        file_path=file_path,
        smells=smells,
        metrics=metrics,
        analysis=data,
    )


def analyze_project(path: str) -> ProjectReport:
    """Analyze a directory or single Python file."""
    files = _discover_files(path)
    reports = [analyze_file(f) for f in files]
    return ProjectReport(files=reports)


def _discover_files(path: str) -> list[str]:
    p = Path(path)
    if p.is_file() and p.suffix == ".py":
        return [str(p)]
    if p.is_dir():
        results: list[str] = []
        for root, dirs, filenames in os.walk(p):
            dirs[:] = [
                d
                for d in dirs
                if d not in ("__pycache__", ".git", ".venv", "node_modules")
            ]
            for fn in sorted(filenames):
                if fn.endswith(".py"):
                    results.append(os.path.join(root, fn))
        return results
    return []
