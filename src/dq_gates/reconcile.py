"""Post-load reconciliation between a source extract and a loaded target."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ReconciliationResult:
    source_rows: int
    target_rows: int
    missing_keys: list = field(default_factory=list)
    unexpected_keys: list = field(default_factory=list)
    control_total_diffs: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (
            self.source_rows == self.target_rows
            and not self.missing_keys
            and not self.unexpected_keys
            and not self.control_total_diffs
        )


def reconcile(
    source: pd.DataFrame,
    target: pd.DataFrame,
    key: str,
    sum_columns: list[str] | None = None,
    tolerance: float = 1e-6,
) -> ReconciliationResult:
    """Compare row counts, key sets and control totals (column sums)."""
    src_keys, tgt_keys = set(source[key]), set(target[key])
    diffs = {}
    for col in sum_columns or []:
        s, t = float(source[col].sum()), float(target[col].sum())
        if abs(s - t) > tolerance:
            diffs[col] = {"source": s, "target": t, "diff": round(t - s, 6)}
    return ReconciliationResult(
        source_rows=len(source),
        target_rows=len(target),
        missing_keys=sorted(src_keys - tgt_keys)[:20],
        unexpected_keys=sorted(tgt_keys - src_keys)[:20],
        control_total_diffs=diffs,
    )
