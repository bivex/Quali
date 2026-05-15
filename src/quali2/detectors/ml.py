"""ML-specific code smell detectors.

Detects: Ambiguous Merge Key, Broken NaN Check, Chain Indexing,
Forward Bypass, Type Blind Conversion, Unnecessary Iteration.
"""

from __future__ import annotations

try:
    from antlr4 import CommonTokenStream, InputStream
    from quali2.antlr.Python3Lexer import Python3Lexer
except ImportError:
    CommonTokenStream = object
    InputStream = object
    Python3Lexer = None

from quali2.domain.models import AnalysisData, Smell, SmellType

FLOAT_NAN_PATTERN_LENGTH = 3


class MLScanner:
    """Helper to scan ML-specific tokens and avoid Data Clumps."""

    def __init__(self, fp: str, tokens: list):
        self.fp = fp
        self.tokens = tokens
        self.n = len(tokens)


def detect_ml_smells(
    data: AnalysisData,
    source: str,
    token_stream: CommonTokenStream | None = None,
) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path
    lines = source.splitlines()

    uses_pandas = any(
        "pandas" in imp.module or imp.alias == "pd" for imp in data.imports
    )
    uses_numpy = any("numpy" in imp.module or imp.alias == "np" for imp in data.imports)
    uses_torch = any("torch" in imp.module for imp in data.imports)

    if not (uses_pandas or uses_numpy or uses_torch):
        return []

    if token_stream is None:
        if Python3Lexer is None:
            return []
        input_stream = InputStream(source)
        lexer = Python3Lexer(input_stream)
        token_stream = CommonTokenStream(lexer)
    token_stream.fill()
    tokens = token_stream.tokens

    scanner = MLScanner(fp, tokens)

    smells.extend(_check_token_smells(scanner, uses_pandas, uses_numpy, uses_torch))
    smells.extend(_check_line_smells(fp, lines, uses_pandas))
    return smells


def _check_token_smells(
    scanner: MLScanner, uses_pandas: bool, uses_numpy: bool, uses_torch: bool
) -> list[Smell]:
    smells: list[Smell] = []
    for i in range(scanner.n):
        t = scanner.tokens[i]
        if (uses_pandas or uses_numpy) and t.type == Python3Lexer.COMPARISON:
            smells.extend(_detect_broken_nan(scanner, i))
        if uses_pandas and t.type == Python3Lexer.LSQB:
            smells.extend(_detect_chain_indexing(scanner, i))
        if uses_pandas and t.type == Python3Lexer.NAME and t.text in ("iterrows", "itertuples"):
            smells.extend(_detect_unnecessary_iteration(scanner, i))
        if uses_torch and t.type == Python3Lexer.DOT:
            smells.extend(_detect_forward_bypass(scanner, i))
    return smells


def _check_line_smells(fp: str, lines: list[str], uses_pandas: bool) -> list[Smell]:
    smells: list[Smell] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if uses_pandas and ".merge(" in stripped and "on=" not in stripped:
            smells.append(
                Smell.create(
                    SmellType.AMBIGUOUS_MERGE_KEY,
                    fp,
                    i,
                    "<line>",
                    "Call to .merge() without explicit 'on=' key",
                )
            )
        if uses_pandas and ".values" in stripped and "dtype" not in stripped:
            if ".values" in stripped and not any(x in stripped for x in (".to_numpy", ".astype")):
                 smells.append(
                    Smell.create(
                        SmellType.TYPE_BLIND_CONVERSION,
                        fp,
                        i,
                        "<line>",
                        "Direct .values access is type-blind; use .to_numpy() or specify dtype",
                    )
                )
    return smells


def _detect_broken_nan(scanner: MLScanner, i: int) -> list[Smell]:
    if i > 0 and _is_nan_token(scanner, i - 1):
        return [
            Smell.create(
                SmellType.BROKEN_NAN_CHECK,
                scanner.fp,
                scanner.tokens[i].line,
                "<comparison>",
                "Direct comparison with NaN always returns False; use pd.isna() or math.isnan()",
            )
        ]
    if i + 1 < scanner.n and _is_nan_token(scanner, i + 1):
        return [
            Smell.create(
                SmellType.BROKEN_NAN_CHECK,
                scanner.fp,
                scanner.tokens[i].line,
                "<comparison>",
                "Direct comparison with NaN always returns False; use pd.isna() or math.isnan()",
            )
        ]
    return []


def _is_nan_token(scanner: MLScanner, j: int) -> bool:
    if j < 0 or j >= scanner.n:
        return False
    t = scanner.tokens[j]
    if t.text in ("nan", "NaN"):
        return True
    if _is_dotted_nan(scanner, j):
        return True
    if _is_float_nan(scanner, j):
        return True
    return False


def _is_dotted_nan(scanner: MLScanner, j: int) -> bool:
    if j + 2 >= scanner.n:
        return False
    tks = scanner.tokens
    if tks[j].text in ("np", "pd", "numpy", "pandas") and tks[j+1].text == "." and tks[j+2].text in ("nan", "NaN", "NA"):
        return True
    return False


def _is_float_nan(scanner: MLScanner, j: int) -> bool:
    if j + FLOAT_NAN_PATTERN_LENGTH >= scanner.n:
        return False
    tks = scanner.tokens
    if (
        tks[j].text == "float"
        and tks[j + 1].text == "("
        and tks[j + 2].text in ("'nan'", '"nan"')
        and tks[j + FLOAT_NAN_PATTERN_LENGTH].text == ")"
    ):
        return True
    return False


def _is_chain_index(scanner: MLScanner, i: int) -> bool:
    if i + 1 >= scanner.n:
        return False
    return scanner.tokens[i].text == "]" and scanner.tokens[i+1].text == "["


def _detect_chain_indexing(scanner: MLScanner, i: int) -> list[Smell]:
    if _is_chain_index(scanner, i):
        return [
            Smell.create(
                SmellType.CHAIN_INDEXING,
                scanner.fp,
                scanner.tokens[i].line,
                "<indexing>",
                "Chained indexing detected; use .loc[] or .iloc[] for safer access",
            )
        ]
    return []


def _is_iter_call(scanner: MLScanner, i: int) -> bool:
    if i + 1 >= scanner.n:
        return False
    return scanner.tokens[i+1].text == "("


def _detect_unnecessary_iteration(scanner: MLScanner, i: int) -> list[Smell]:
    if _is_iter_call(scanner, i):
        return [
            Smell.create(
                SmellType.UNNECESSARY_ITERATION,
                scanner.fp,
                scanner.tokens[i].line,
                scanner.tokens[i].text,
                f"Row-based iteration with .{scanner.tokens[i].text}() is slow; use vectorized operations",
            )
        ]
    return []


def _is_forward_call(scanner: MLScanner, i: int) -> bool:
    if i + 2 >= scanner.n:
        return False
    tks = scanner.tokens
    return tks[i].text == "." and tks[i+1].text == "forward" and tks[i+2].text == "("


def _detect_forward_bypass(scanner: MLScanner, i: int) -> list[Smell]:
    if _is_forward_call(scanner, i):
        return [
            Smell.create(
                SmellType.FORWARD_BYPASS,
                scanner.fp,
                scanner.tokens[i].line,
                "forward",
                "Direct call to .forward() bypasses hooks; call the model object instead",
            )
        ]
    return []
