"""ML-specific code smell detectors.

Detects: Ambiguous Merge Key, Broken NaN Check, Chain Indexing,
Forward Bypass, Type Blind Conversion, Unnecessary Iteration.
"""

from __future__ import annotations

from antlr4 import CommonTokenStream, InputStream

from quali2.antlr.Python3Lexer import Python3Lexer
from quali2.domain.models import AnalysisData, Smell, SmellType


def detect_ml_smells(
    data: AnalysisData,
    source: str,
    token_stream: CommonTokenStream | None = None,
) -> list[Smell]:
    smells: list[Smell] = []
    fp = data.file_path
    lines = source.splitlines()

    # Check if file uses ML libraries
    uses_pandas = any(
        "pandas" in imp.module or imp.alias == "pd" for imp in data.imports
    )
    uses_numpy = any("numpy" in imp.module or imp.alias == "np" for imp in data.imports)
    uses_torch = any("torch" in imp.module for imp in data.imports)

    if not (uses_pandas or uses_numpy or uses_torch):
        return smells

    # Build token list
    if token_stream is None:
        token_stream = CommonTokenStream(Python3Lexer(InputStream(source)))
    token_stream.fill()
    tokens = token_stream.tokens

    # ── Token-stream based checks ──────────────────────────────────────
    if uses_pandas or uses_numpy:
        smells.extend(_detect_broken_nan(fp, tokens))
    if uses_pandas:
        smells.extend(_detect_chain_indexing(fp, tokens))
        smells.extend(_detect_unnecessary_iteration(fp, tokens))
    if uses_torch:
        smells.extend(_detect_forward_bypass(fp, tokens))

    # ── Line-based checks ──────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Ambiguous Merge Key — .merge() without 'on='
        if (
            uses_pandas
            and ".merge(" in stripped
            and "on=" not in stripped
            and "on =" not in stripped
        ):
            smells.append(
                Smell.create(
                    SmellType.AMBIGUOUS_MERGE_KEY,
                    fp,
                    i,
                    "<line>",
                    "merge() called without explicit 'on' parameter — may use unintended join keys",
                )
            )

        # Type Blind Conversion — .values on mixed-type DataFrame
        if uses_pandas and ".values" in stripped and "dtype" not in stripped:
            smells.append(
                Smell.create(
                    SmellType.TYPE_BLIND_CONVERSION,
                    fp,
                    i,
                    "<line>",
                    "Accessing .values on DataFrame with potential mixed types — consider .to_numpy()",
                )
            )

    return smells


# ---------------------------------------------------------------------------
# Token-stream helpers
# ---------------------------------------------------------------------------


def _detect_broken_nan(fp: str, tokens: list) -> list[Smell]:
    """NAME == nan | NAME.nan | float('nan')"""
    smells = []
    n = len(tokens)
    seen_lines: set[int] = set()
    for i, tok in enumerate(tokens):
        if tok.type != Python3Lexer.EQUALS:
            continue
        if tok.line in seen_lines:
            continue
        j = i + 1
        if j >= n:
            continue
        nt = tokens[j]
        is_nan = False
        # NAME (nan or NaN)
        if nt.type == Python3Lexer.NAME and nt.text in ('nan', 'NaN'):
            is_nan = True
        # NAME.nan  (e.g. np.nan, math.nan)
        elif (nt.type == Python3Lexer.NAME
              and j + 2 < n
              and tokens[j + 1].type == Python3Lexer.DOT
              and tokens[j + 2].type == Python3Lexer.NAME
              and tokens[j + 2].text == 'nan'):
            is_nan = True
        # float('nan')
        elif (nt.type == Python3Lexer.NAME and nt.text == 'float'
              and j + 3 < n
              and tokens[j + 1].type == Python3Lexer.OPEN_PAREN
              and tokens[j + 2].type == Python3Lexer.STRING
              and 'nan' in tokens[j + 2].text.lower()):
            is_nan = True
        if is_nan:
            seen_lines.add(tok.line)
            smells.append(Smell.create(
                SmellType.BROKEN_NAN_CHECK, fp, tok.line, "<line>",
                "Direct comparison with NaN always returns False — use math.isnan() or pd.isna()",
            ))
    return smells


def _detect_chain_indexing(fp: str, tokens: list) -> list[Smell]:
    """NAME [ STRING ] [ STRING ]"""
    smells = []
    n = len(tokens)
    seen_lines: set[int] = set()
    for i in range(n - 5):
        if (tokens[i].type == Python3Lexer.NAME
                and tokens[i + 1].type == Python3Lexer.OPEN_BRACK
                and tokens[i + 2].type == Python3Lexer.STRING
                and tokens[i + 3].type == Python3Lexer.CLOSE_BRACK
                and tokens[i + 4].type == Python3Lexer.OPEN_BRACK
                and tokens[i + 5].type == Python3Lexer.STRING):
            line = tokens[i].line
            if line not in seen_lines:
                seen_lines.add(line)
                smells.append(Smell.create(
                    SmellType.CHAIN_INDEXING, fp, line, "<line>",
                    f"Chained indexing on DataFrame: {tokens[i].text}[...][...] — use .loc[] instead",
                ))
    return smells


def _detect_unnecessary_iteration(fp: str, tokens: list) -> list[Smell]:
    """FOR ... IN NAME . iterrows/itertuples ()"""
    ITER_METHODS = frozenset({'iterrows', 'itertuples'})
    smells = []
    n = len(tokens)
    seen_lines: set[int] = set()
    for i, tok in enumerate(tokens):
        if tok.type != Python3Lexer.FOR or tok.line in seen_lines:
            continue
        # Find IN token
        j = i + 1
        while j < n and tokens[j].type != Python3Lexer.IN:
            j += 1
        if j >= n:
            continue
        k = j + 1
        if (k + 3 < n
                and tokens[k].type == Python3Lexer.NAME
                and tokens[k + 1].type == Python3Lexer.DOT
                and tokens[k + 2].type == Python3Lexer.NAME
                and tokens[k + 2].text in ITER_METHODS
                and tokens[k + 3].type == Python3Lexer.OPEN_PAREN):
            line = tok.line
            seen_lines.add(line)
            smells.append(Smell.create(
                SmellType.UNNECESSARY_ITERATION, fp, line, "<line>",
                f"Iterating over DataFrame '{tokens[k].text}' — prefer vectorized operations",
            ))
    return smells


def _detect_forward_bypass(fp: str, tokens: list) -> list[Smell]:
    """NAME . forward ("""
    smells = []
    n = len(tokens)
    seen_lines: set[int] = set()
    for i in range(n - 3):
        if (tokens[i].type == Python3Lexer.NAME
                and tokens[i + 1].type == Python3Lexer.DOT
                and tokens[i + 2].type == Python3Lexer.NAME
                and tokens[i + 2].text == 'forward'
                and tokens[i + 3].type == Python3Lexer.OPEN_PAREN):
            line = tokens[i].line
            if line not in seen_lines:
                seen_lines.add(line)
                smells.append(Smell.create(
                    SmellType.FORWARD_BYPASS, fp, line, "<line>",
                    f"Calling .forward() directly on '{tokens[i].text}' — use model(input) instead to trigger hooks and autocast",
                ))
    return smells
