# Quali2

Python code quality assessment tool powered by ANTLR4. Detects architecture smells, design smells, implementation smells, and ML-specific code smells. Computes object-oriented metrics.

## Features

**30 smell detectors** across four categories:

| Category | Count | Smells |
|---|---|---|
| Architecture | 4 | God Component, Feature Concentration, Dense Structure, Unstable Dependency |
| Design | 10 | Multifaceted Abstraction, Feature Envy, Deficient Encapsulation, Insufficient/Broken/Hub-like Modularization, Wide/Deep/Rebellious/Broken Hierarchy |
| Implementation | 11 | Complex Conditional, Complex Method, Empty Catch Clause, Long Identifier, Long Method, Long Parameter List, Long Statement, Magic Number, Missing Default, Long Lambda, Long Message Chain |
| ML | 6 | Ambiguous Merge Key, Broken NaN Check, Chain Indexing, Forward Bypass, Type Blind Conversion, Unnecessary Iteration |

**11 OO metrics** per file/class/method:

| Metric | Scope | Description |
|---|---|---|
| LOC | file, method | Lines of code |
| CC | method | Cyclomatic complexity |
| PC | method | Parameter count |
| NOF | class | Number of fields |
| NOPF | class | Number of public fields |
| NOM | class | Number of methods |
| NOPM | class | Number of public methods |
| WMC | class | Weighted methods per class |
| DIT | class | Depth of inheritance tree |
| LCOM | class | Lack of cohesion of methods |
| FANOUT | module | Number of outgoing module dependencies |

## Installation

```bash
git clone <repo-url> && cd quali2
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+ and Java 17+ (for ANTLR4 grammar generation; not needed at runtime).

## Usage

```bash
# Analyze a single file
quali2 path/to/file.py

# Analyze a directory (recursively)
quali2 src/

# JSON output
quali2 src/ --format json

# Version
quali2 --version
```

Or run without installing:

```bash
source .venv/bin/activate
PYTHONPATH=src python -m quali2 path/to/code.py
```

### Example output

```
========================================================================
  src/myapp/models.py
========================================================================

  Smells (3):
    [!!] L  14  [Design] Broken Hierarchy
          class Child: Subclass defines __init__ but does not call super().__init__()
    [! ] L  42  [Implementation] Long Parameter List
          __init__: Method has 9 parameters (threshold 7)
    [!!] L  88  [ML] Chain Indexing
          <line>: Chained indexing on DataFrame: df["a"]["b"] -- use .loc[] instead

  Metrics:
    <file>                                    LOC    = 120
    <module>                                  FANOUT = 5
    class Animal                              NOF    = 7
    class Animal                              NOM    = 12
    class Animal                              WMC    = 12
    class Animal                              DIT    = 0
    class Animal                              LCOM   = 1.0

========================================================================
  Summary
========================================================================
  Files analyzed : 1
  Total smells   : 3
  Total metrics  : 42
    High    : 2
    Medium  : 1
```

## Architecture

```
src/quali2/
├── domain/
│   └── models.py              Value objects (Smell, Metric, enums, reports)
├── analysis/
│   ├── engine.py              Orchestration: parse -> metrics -> detect -> report
│   ├── visitor.py             ANTLR4 parse-tree visitor (structural extraction)
│   └── metrics.py             OO metrics computation
├── detectors/
│   ├── architecture.py        Architecture smells (incl. cross-file analysis)
│   ├── design.py              Design smells
│   ├── implementation.py      Implementation smells (incl. magic number via ANTLR4 tokens)
│   └── ml.py                  ML-specific smells
├── reporting.py               Text and JSON output formatters
├── cli.py                     CLI entry point
└── antlr/                     ANTLR4-generated Python3 lexer/parser
```

Pipeline:

1. **Parse** -- ANTLR4 lexer/parser converts Python source into a parse tree
2. **Visit** -- `PythonAnalysisVisitor` walks the tree, extracting classes, methods, imports, fields, inheritance
3. **Metrics** -- `compute_metrics()` calculates OO metrics from the extracted data
4. **Detect** -- Four detector modules run per-file; cross-file detectors run on the full project
5. **Report** -- `format_text()` or `format_json()` renders results

## Detection Thresholds

Each detector uses configurable thresholds defined as module-level constants:

| Smell | Threshold | Constant |
|---|---|---|
| God Component (LOC) | > 1000 lines | `GOD_COMPONENT_LOC` |
| God Component (classes) | > 10 classes | `GOD_COMPONENT_CLASSES` |
| Feature Concentration | > 10 import modules | `FEATURE_CONCENTRATION_IMPORT_MODULES` |
| Dense Structure | avg > 10 attr accesses/method | `DENSE_STRUCTURE_AVG_ACCESSES` |
| Unstable Dependency | instability I > 0.4 | `UNSTABLE_DEPENDENCY_THRESHOLD` |
| Broken Modularization | 6+ shared local imports | `BROKEN_MODULARIZATION_SHARED_IMPORTS` |
| Multifaceted Abstraction | > 15 methods | `MULTIFACETED_METHODS` |
| Deficient Encapsulation | > 5 public fields | (inline) |
| Insufficient Modularization | > 500 lines | `INSUFFICIENT_LOC` |
| Hub-like Modularization | > 15 base classes | `HUB_LIKE_FAN` |
| Wide Hierarchy | >= 10 subclasses | `WIDE_HIERARCHY_CHILDREN` |
| Deep Hierarchy | >= 5 depth | `DEEP_HIERARCHY_DEPTH` |
| Rebellious Hierarchy | > 5 overrides, < 2 fields | (inline) |
| Broken Hierarchy | `__init__` without `super()` | (inline, source-based) |
| Long Method | > 40 lines | `LONG_METHOD_LINES` |
| Long Parameter List | > 7 params | `LONG_PARAM_LIST` |
| Complex Method | CC > 15 | `COMPLEX_METHOD_CC` |
| Complex Conditional | 4+ boolean ops | `COMPLEX_CONDITIONAL_BOOLEAN_OPS` |
| Long Identifier | > 40 chars | `LONG_IDENTIFIER_CHARS` |
| Long Statement | > 120 chars | `LONG_STATEMENT_CHARS` |
| Long Lambda | > 5 lines | `LONG_LAMBDA_LINES` |
| Long Message Chain | >= 4 dots | `LONG_MESSAGE_CHAIN_DOTS` |
| Magic Number | non-whitelisted numeric literal | `WHITELISTED_NUMBERS` |
| Missing Default | `match` without `case _` | (regex) |
| Ambiguous Merge Key | `.merge()` without `on=` | (inline) |
| Broken NaN Check | `x == np.nan` | (regex) |
| Chain Indexing | `df["a"]["b"]` | (regex) |
| Forward Bypass | `model.forward(x)` | (regex) |
| Type Blind Conversion | `.values` without `dtype` | (inline) |
| Unnecessary Iteration | `.iterrows()` / `.itertuples()` | (regex) |

## Testing

```bash
source .venv/bin/activate
PYTHONPATH=src pytest tests/ -v
```

**131 tests**, all passing. Coverage matrix:

### Architecture -- 13 tests

| Detector | Test Class | +Case | -Case |
|---|---|---|---|
| God Component (LOC) | `TestGodComponent` | ✓ | ✓ |
| God Component (classes) | `TestGodComponent` / `TestGodComponentNegative` | ✓ | ✓ |
| Feature Concentration | `TestFeatureConcentration` | ✓ | ✓ |
| Dense Structure | `TestDenseStructure` | ✓ | ✓ |
| Unstable Dependency (cross-file) | `TestUnstableDependency` | ✓ | ✓, ✓ |
| Broken Modularization (cross-file) | `TestBrokenModularization` | ✓ | ✓ |

### Design -- 16 tests

| Detector | Test Class | +Case | -Case |
|---|---|---|---|
| Multifaceted Abstraction | `TestMultifacetedAbstraction` | ✓ | ✓ |
| Feature Envy | `TestFeatureEnvy` / `TestFeatureEnvyNegative` | ✓ | ✓ |
| Deficient Encapsulation | `TestDeficientEncapsulation` | ✓ | ✓ |
| Insufficient Modularization | `TestInsufficientModularization` | ✓ | ✓ |
| Hub-like Modularization | `TestHubLikeModularization` / `TestHubLikeNegative` | ✓ | ✓ |
| Deep Hierarchy | `TestDeepHierarchy` | ✓ | ✓ |
| Wide Hierarchy | `TestWideHierarchy` | ✓ | ✓ |
| Rebellious Hierarchy | `TestRebelliousHierarchy` / `TestRebelliousHierarchyNegative` | ✓ | ✓ |
| Broken Hierarchy | `TestBrokenHierarchy` | ✓ | ✓ |

### Implementation -- 41 tests

| Detector | Test Class | +Case | -Case |
|---|---|---|---|
| Complex Conditional | `TestComplexConditional` | ✓ | ✓ |
| Complex Method | `TestComplexMethod` / `TestComplexMethodNegative` | ✓ | ✓ |
| Empty Catch Clause | `TestEmptyCatchClause` | ✓, ✓ | ✓ |
| Long Identifier | `TestLongIdentifier` | ✓ | ✓ |
| Long Method | `TestLongMethod` | ✓ | ✓ |
| Long Parameter List | `TestLongParameterList` | ✓ | ✓ |
| Long Statement | `TestLongStatement` | ✓ | ✓ |
| Magic Number | `TestMagicNumber` / `TestMagicNumberEdgeCases` | 12 | 8 |
| Missing Default | `TestMissingDefault` | ✓ | ✓ |
| Long Lambda Function | `TestLongLambdaFunction` | ✓ | ✓ |
| Long Message Chain | `TestLongMessageChain` | ✓ | ✓ |

### ML -- 11 tests

| Detector | Test Class | +Case | -Case |
|---|---|---|---|
| Ambiguous Merge Key | `TestAmbiguousMergeKey` | ✓ | ✓ |
| Broken NaN Check | `TestBrokenNaNCheck` | ✓, ✓ | ✓ |
| Chain Indexing | `TestChainIndexing` | ✓ | ✓ |
| Forward Bypass | `TestForwardBypass` | ✓ | ✓ |
| Type Blind Conversion | `TestTypeBlindConversion` | ✓ | ✓ |
| Unnecessary Iteration | `TestUnnecessaryIteration` | ✓, ✓ | ✓ |

### Metrics, CLI, Infrastructure -- 44 tests

| Area | Test Class | Tests |
|---|---|---|
| OO metrics edge cases (LCOM, DIT, FANOUT, CC, NOM, NOPF) | `TestMetricsEdgeCases` | 6 |
| Clean code -> no false positives | `TestCleanCode` | 3 |
| Smell metadata (category/severity) | `TestSmellMetadata` | 8 |
| Report aggregation | `TestReportAggregation` | 3 |
| CLI errors, json, version | `TestCLIErrors` | 3 |
| JSON content verification | `TestReportingContent` | 2 |
| Visitor: from-import, nested class, defaults, async | `TestVisitorEdgeCases` | 5 |
| File discovery: .pyc, nested dirs, __pycache__ | `TestFileDiscovery` | 3 |
| Parse error resilience | `TestParseErrorResilience` | 1 |
| Original smoke tests | `test_quali2.py` | 9 |

## Dependencies

- **Runtime**: `antlr4-python3-runtime` 4.13+
- **Build**: `hatchling`
- **Dev**: `pytest`

## License

MIT
