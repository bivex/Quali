"""Tests for Fowler's Refactoring code smell detectors."""

from __future__ import annotations

import os
import tempfile
import pytest

from quali2.analysis.engine import analyze_file
from quali2.domain.models import Smell


def _analyze(code: str) -> list[Smell]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            report = analyze_file(f.name)
            return report.smells
        finally:
            os.unlink(f.name)


def _smells_of(code: str, smell_type: str) -> list[Smell]:
    return [s for s in _analyze(code) if s.smell_type.value == smell_type]


class TestSwitchStatements:
    def test_triggered_match(self):
        code = """
def f(x):
    match x:
        case 1: pass
        case 2: pass
        case 3: pass
        case 4: pass
        case 5: pass
        case 6: pass
"""
        smells = _smells_of(code, "Switch Statements")
        assert len(smells) >= 1

    def test_triggered_if_elif(self):
        code = """
def f(x):
    if x == 1: pass
    elif x == 2: pass
    elif x == 3: pass
    elif x == 4: pass
    elif x == 5: pass
    elif x == 6: pass
    else: pass
"""
        smells = _smells_of(code, "Switch Statements")
        assert len(smells) >= 1

    def test_not_triggered_short(self):
        code = """
def f(x):
    if x == 1: pass
    else: pass
"""
        smells = _smells_of(code, "Switch Statements")
        assert len(smells) == 0


class TestMessageChains:
    def test_triggered(self):
        code = "def f(x): return x.a.b.c.d.e"
        smells = _smells_of(code, "Long Message Chain")
        assert len(smells) >= 1


class TestDataClumps:
    def test_triggered(self):
        code = """
def f1(a, b, c, d): pass
def f2(a, b, c, e): pass
"""
        # (a, b, c) is a clump if it appears in 2+ functions
        smells = _smells_of(code, "Data Clumps")
        assert len(smells) >= 2

    def test_not_triggered_unique(self):
        code = """
def f1(a, b, c): pass
def f2(x, y, z): pass
"""
        smells = _smells_of(code, "Data Clumps")
        assert len(smells) == 0


class TestFeatureEnvy:
    def test_triggered(self):
        code = """
class C:
    def __init__(self):
        self.x = 1
    def envies(self, other):
        return other.a + other.b + other.c + other.d + other.e
"""
        smells = _smells_of(code, "Feature Envy")
        assert len(smells) >= 1


class TestPrimitiveObsession:
    def test_triggered_annotations(self):
        code = """
def f(a: int, b: str, c: float, d: bool, e: bytes):
    pass
"""
        smells = _smells_of(code, "Primitive Obsession")
        assert len(smells) >= 1

    def test_triggered_defaults(self):
        code = """
def f(a=1, b="s", c=1.0, d=True, e=b""):
    pass
"""
        smells = _smells_of(code, "Primitive Obsession")
        assert len(smells) >= 1


class TestMiddleMan:
    def test_triggered(self):
        code = """
class MiddleMan:
    def __init__(self, other):
        self.other = other
    def m1(self): return self.other.m1()
    def m2(self): return self.other.m2()
    def m3(self): return self.other.m3()
    def m4(self): return self.other.m4()
"""
        smells = _smells_of(code, "Middle Man")
        assert len(smells) >= 1


class TestSpeculativeGenerality:
    def test_unused_parameter(self):
        code = "def f(a, b): return a"
        smells = _smells_of(code, "Speculative Generality")
        assert any("unused parameter 'b'" in s.message.lower() for s in smells)


class TestDivergentChange:
    def test_triggered(self):
        # Many methods, low cohesion
        methods = ""
        for i in range(12):
            methods += f"    def m{i}(self): return self.f{i}\n"
        fields = "        " + "; ".join(f"self.f{i} = {i}" for i in range(12))
        code = f"""
class Divergent:
    def __init__(self):
{fields}
{methods}
"""
        smells = _smells_of(code, "Divergent Change")
        assert len(smells) >= 1


class TestShotgunSurgery:
    def test_triggered(self):
        code = """
class Surgery:
    def m(self, o):
        return o.a1 + o.a2 + o.a3 + o.a4 + o.a5 + o.a6 + o.a7 + o.a8 + o.a9 + o.a10 + o.a11
"""
        smells = _smells_of(code, "Shotgun Surgery")
        assert len(smells) >= 1


class TestTemporaryField:
    def test_triggered(self):
        code = """
class Temp:
    def __init__(self):
        self.temp_field = 1
    def use_it(self):
        return self.temp_field
    def other(self):
        return 1
"""
        smells = _smells_of(code, "Temporary Field")
        assert len(smells) >= 1


class TestRefusedBequest:
    def test_triggered(self):
        code = """
class Sub(Base):
    def ignored(self):
        raise NotImplementedError()
"""
        smells = _smells_of(code, "Refused Bequest")
        assert len(smells) >= 1


class TestCommentDensity:
    def test_triggered(self):
        code = """
# This is a comment
# Another comment
# More comments
# Too many comments
# Way too many
# Please stop
def f():
    pass
"""
        smells = _smells_of(code, "Comment Density")
        assert len(smells) >= 1
