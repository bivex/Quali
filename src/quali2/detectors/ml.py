"""ML-specific code smell detectors.

Detects: Ambiguous Merge Key, Broken NaN Check, Chain Indexing,
Forward Bypass, Type Blind Conversion, Unnecessary Iteration.
"""

from __future__ import annotations

import re

from quali2.domain.models import AnalysisData, Smell, SmellType


def detect_ml_smells(data: AnalysisData, source: str) -> list[Smell]:
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

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # --- Pandas smells ---

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

        # Broken NaN Check — 'x == NaN' or 'x == np.nan'
        if uses_pandas or uses_numpy:
            nan_compare = re.search(
                r"(\w+)\s*==\s*(?:np\.nan|float\('nan'\)|NaN)", stripped
            )
            if nan_compare:
                smells.append(
                    Smell.create(
                        SmellType.BROKEN_NAN_CHECK,
                        fp,
                        i,
                        "<line>",
                        f"Direct comparison with NaN ('{nan_compare.group(0)}') always returns False — use math.isnan() or pd.isna()",
                    )
                )

        # Chain Indexing — df['x']['y'] pattern
        if uses_pandas:
            chain = re.search(
                r"(\w+)\[(['\"][\w.]+['\"])\]\[(['\"][\w.]+['\"])\]", stripped
            )
            if chain:
                smells.append(
                    Smell.create(
                        SmellType.CHAIN_INDEXING,
                        fp,
                        i,
                        "<line>",
                        f"Chained indexing on DataFrame: {chain.group(0)} — use .loc[] instead",
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

        # Unnecessary Iteration — iterating over DataFrame rows
        if uses_pandas:
            iter_patterns = [
                r"for\s+\w+\s*,\s*\w+\s+in\s+(\w+)\.iterrows\(\)",
                r"for\s+\w+\s+in\s+(\w+)\.itertuples\(\)",
                r"for\s+\w+\s+in\s+range\(len\((\w+)\)\).*\1\[",
            ]
            for pat in iter_patterns:
                match = re.search(pat, stripped)
                if match:
                    smells.append(
                        Smell.create(
                            SmellType.UNNECESSARY_ITERATION,
                            fp,
                            i,
                            "<line>",
                            f"Iterating over DataFrame '{match.group(1)}' — prefer vectorized operations",
                        )
                    )

        # --- PyTorch smells ---

        # Forward Bypass — model.forward() called directly
        if uses_torch:
            forward_bypass = re.search(r"(\w+)\.forward\(", stripped)
            if forward_bypass:
                smells.append(
                    Smell.create(
                        SmellType.FORWARD_BYPASS,
                        fp,
                        i,
                        "<line>",
                        f"Calling .forward() directly on '{forward_bypass.group(1)}' — use model(input) instead to trigger hooks and autocast",
                    )
                )

    return smells
