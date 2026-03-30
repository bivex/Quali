"""Tests for Quali2."""

import json
import os
import tempfile

import pytest


SAMPLE_CODE = '''\
"""Sample module."""

import os
import sys

CONSTANT = 42


class MyClass:
    x = 1
    y = 2
    public_field = 3

    def __init__(self, a, b, c, d, e, f, g, h, i):
        self.a = a
        self.b = b
        self.c = c

    def method1(self):
        return self.a + self.b

    def method2(self):
        return self.c


def top_func():
    try:
        x = int("bad")
    except ValueError:
        pass
    return x
'''


@pytest.fixture
def sample_file(tmp_path):
    fp = tmp_path / "sample.py"
    fp.write_text(SAMPLE_CODE)
    return str(fp)


def test_analyze_file_returns_report(sample_file):
    from quali2.analysis.engine import analyze_file

    report = analyze_file(sample_file)
    assert report.file_path == sample_file
    assert len(report.smells) > 0
    assert len(report.metrics) > 0


def test_smell_types_detected(sample_file):
    from quali2.analysis.engine import analyze_file

    report = analyze_file(sample_file)
    smell_types = {s.smell_type.value for s in report.smells}

    assert "Long Parameter List" in smell_types
    assert "Empty Catch Clause" in smell_types


def test_metrics_computed(sample_file):
    from quali2.analysis.engine import analyze_file

    report = analyze_file(sample_file)
    metric_names = {(m.element, m.name) for m in report.metrics}

    assert ("<file>", "LOC") in metric_names
    assert ("<module>", "FANOUT") in metric_names
    assert ("class MyClass", "NOF") in metric_names
    assert ("class MyClass", "NOM") in metric_names
    assert ("class MyClass", "WMC") in metric_names
    assert ("class MyClass", "DIT") in metric_names
    assert ("class MyClass", "LCOM") in metric_names


def test_json_output(sample_file):
    from quali2.analysis.engine import analyze_file
    from quali2.domain.models import ProjectReport
    from quali2.reporting import format_json

    report = analyze_file(sample_file)
    project = ProjectReport(files=[report])
    output = format_json(project)
    data = json.loads(output)
    assert "files" in data
    assert "summary" in data
    assert data["summary"]["files_analyzed"] == 1


def test_text_output(sample_file):
    from quali2.analysis.engine import analyze_file
    from quali2.domain.models import ProjectReport
    from quali2.reporting import format_text

    report = analyze_file(sample_file)
    project = ProjectReport(files=[report])
    output = format_text(project)
    assert "Smells" in output
    assert "Metrics" in output
    assert "Summary" in output


def test_project_analysis(tmp_path):
    from quali2.analysis.engine import analyze_project

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")

    report = analyze_project(str(tmp_path))
    assert len(report.files) == 2


def test_empty_except_detected(sample_file):
    from quali2.analysis.engine import analyze_file

    report = analyze_file(sample_file)
    empty_catches = [
        s for s in report.smells if s.smell_type.value == "Empty Catch Clause"
    ]
    assert len(empty_catches) >= 1


def test_ml_smells():
    from quali2.analysis.engine import analyze_file

    code = """\
import pandas as pd
import numpy as np

df = pd.DataFrame({"a": [1, np.nan]})
check = df == np.nan
merged = df.merge(df)
chain = df["a"]["b"]
for i, row in df.iterrows():
    print(row)
vals = df.values
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            report = analyze_file(f.name)
            smell_types = {s.smell_type.value for s in report.smells}
            assert "Broken NaN Check" in smell_types
            assert "Ambiguous Merge Key" in smell_types
            assert "Chain Indexing" in smell_types
            assert "Unnecessary Iteration" in smell_types
            assert "Type Blind Conversion" in smell_types
        finally:
            os.unlink(f.name)


def test_cli_main(sample_file, capsys):
    from quali2.cli import main

    main([sample_file])
    captured = capsys.readouterr()
    assert "Smells" in captured.out
