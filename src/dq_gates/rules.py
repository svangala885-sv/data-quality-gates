"""Rule implementations.

Each rule takes a pandas DataFrame and returns a RuleResult. Rules are built
from plain dictionaries (loaded from YAML) so that checks live in config, not
in pipeline code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

import pandas as pd

SEVERITIES = ("error", "warn")


@dataclass
class RuleResult:
    name: str
    rule_type: str
    column: str | None
    severity: str
    passed: bool
    failed_rows: int
    total_rows: int
    detail: str
    sample_failures: list[Any] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        return self.failed_rows / self.total_rows if self.total_rows else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rule_type": self.rule_type,
            "column": self.column,
            "severity": self.severity,
            "passed": self.passed,
            "failed_rows": self.failed_rows,
            "total_rows": self.total_rows,
            "failure_rate": round(self.failure_rate, 6),
            "detail": self.detail,
            "sample_failures": [str(v) for v in self.sample_failures],
        }


RuleFn = Callable[[pd.DataFrame], RuleResult]


def _require_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise KeyError(f"column '{column}' not found; available: {list(df.columns)}")


def _result(spec: dict, rule_type: str, df: pd.DataFrame, mask: pd.Series, detail: str) -> RuleResult:
    """Build a result from a boolean mask where True marks a failing row."""
    failed = int(mask.sum())
    total = len(df)
    max_rate = float(spec.get("max_failure_rate", 0.0))
    passed = failed == 0 or (total > 0 and failed / total <= max_rate)
    column = spec.get("column")
    sample = df.loc[mask, column].head(5).tolist() if column and failed else []
    return RuleResult(
        name=spec.get("name", f"{rule_type}:{column}"),
        rule_type=rule_type,
        column=column,
        severity=spec.get("severity", "error"),
        passed=passed,
        failed_rows=failed,
        total_rows=total,
        detail=detail,
        sample_failures=sample,
    )


def not_null(spec: dict) -> RuleFn:
    col = spec["column"]

    def check(df: pd.DataFrame) -> RuleResult:
        _require_column(df, col)
        return _result(spec, "not_null", df, df[col].isna(), f"{col} must not be null")

    return check


def unique(spec: dict) -> RuleFn:
    cols = spec.get("columns") or [spec["column"]]

    def check(df: pd.DataFrame) -> RuleResult:
        for c in cols:
            _require_column(df, c)
        mask = df.duplicated(subset=cols, keep=False)
        spec_with_col = {**spec, "column": spec.get("column", cols[0])}
        return _result(spec_with_col, "unique", df, mask, f"{cols} must be unique")

    return check


def in_range(spec: dict) -> RuleFn:
    col = spec["column"]
    lo, hi = spec.get("min"), spec.get("max")

    def check(df: pd.DataFrame) -> RuleResult:
        _require_column(df, col)
        values = pd.to_numeric(df[col], errors="coerce")
        mask = values.isna() & df[col].notna()  # non-numeric values fail
        if lo is not None:
            mask |= values < lo
        if hi is not None:
            mask |= values > hi
        return _result(spec, "in_range", df, mask, f"{col} must be within [{lo}, {hi}]")

    return check


def accepted_values(spec: dict) -> RuleFn:
    col = spec["column"]
    allowed = set(spec["values"])

    def check(df: pd.DataFrame) -> RuleResult:
        _require_column(df, col)
        mask = df[col].notna() & ~df[col].isin(allowed)
        return _result(spec, "accepted_values", df, mask, f"{col} must be one of {sorted(allowed)}")

    return check


def regex(spec: dict) -> RuleFn:
    col = spec["column"]
    pattern = re.compile(spec["pattern"])

    def check(df: pd.DataFrame) -> RuleResult:
        _require_column(df, col)
        present = df[col].notna()
        matches = pd.Series(False, index=df.index)
        matches[present] = [bool(pattern.fullmatch(str(v))) for v in df.loc[present, col]]
        mask = present & ~matches
        return _result(spec, "regex", df, mask, f"{col} must match {pattern.pattern}")

    return check


def row_count(spec: dict) -> RuleFn:
    lo, hi = spec.get("min", 0), spec.get("max")

    def check(df: pd.DataFrame) -> RuleResult:
        n = len(df)
        ok = n >= lo and (hi is None or n <= hi)
        return RuleResult(
            name=spec.get("name", "row_count"),
            rule_type="row_count",
            column=None,
            severity=spec.get("severity", "error"),
            passed=ok,
            failed_rows=0 if ok else 1,
            total_rows=n,
            detail=f"row count {n} must be within [{lo}, {hi}]",
        )

    return check


def freshness(spec: dict) -> RuleFn:
    """Fail when the newest timestamp is older than max_age_hours relative to as_of."""
    col = spec["column"]
    max_age = pd.Timedelta(hours=float(spec["max_age_hours"]))

    def check(df: pd.DataFrame) -> RuleResult:
        _require_column(df, col)
        ts = pd.to_datetime(df[col], errors="coerce", utc=True)
        as_of = pd.Timestamp(spec["as_of"], tz="UTC") if spec.get("as_of") else pd.Timestamp.now(tz="UTC")
        newest = ts.max()
        ok = pd.notna(newest) and (as_of - newest) <= max_age
        return RuleResult(
            name=spec.get("name", f"freshness:{col}"),
            rule_type="freshness",
            column=col,
            severity=spec.get("severity", "error"),
            passed=bool(ok),
            failed_rows=0 if ok else 1,
            total_rows=len(df),
            detail=f"newest {col}={newest} must be within {max_age} of {as_of}",
        )

    return check


RULES: dict[str, Callable[[dict], RuleFn]] = {
    "not_null": not_null,
    "unique": unique,
    "in_range": in_range,
    "accepted_values": accepted_values,
    "regex": regex,
    "row_count": row_count,
    "freshness": freshness,
}


def build_rule(spec: dict) -> RuleFn:
    rule_type = spec.get("type")
    if rule_type not in RULES:
        raise ValueError(f"unknown rule type '{rule_type}'; supported: {sorted(RULES)}")
    if spec.get("severity", "error") not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}")
    return RULES[rule_type](spec)
