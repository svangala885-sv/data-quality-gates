"""A quality gate evaluates a set of rules and blocks the load on error-level failures."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .rules import RuleResult, build_rule

log = logging.getLogger(__name__)


class QualityGateFailed(RuntimeError):
    """Raised when one or more error-severity rules fail."""

    def __init__(self, result: GateResult):
        self.result = result
        failed = ", ".join(r.name for r in result.blocking_failures)
        super().__init__(f"quality gate '{result.dataset}' failed: {failed}")


@dataclass
class GateResult:
    dataset: str
    results: list[RuleResult]

    @property
    def blocking_failures(self) -> list[RuleResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]

    @property
    def warnings(self) -> list[RuleResult]:
        return [r for r in self.results if not r.passed and r.severity == "warn"]

    @property
    def passed(self) -> bool:
        return not self.blocking_failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "passed": self.passed,
            "rules_evaluated": len(self.results),
            "blocking_failures": len(self.blocking_failures),
            "warnings": len(self.warnings),
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class QualityGate:
    def __init__(self, dataset: str, rule_specs: list[dict]):
        if not rule_specs:
            raise ValueError("a quality gate needs at least one rule")
        self.dataset = dataset
        self.rule_specs = rule_specs
        self._rules = [build_rule(spec) for spec in rule_specs]

    @classmethod
    def from_yaml(cls, path: str | Path) -> QualityGate:
        config = yaml.safe_load(Path(path).read_text())
        return cls(dataset=config["dataset"], rule_specs=config["rules"])

    def evaluate(self, df: pd.DataFrame) -> GateResult:
        results: list[RuleResult] = []
        for spec, rule in zip(self.rule_specs, self._rules):
            try:
                results.append(rule(df))
            except Exception as exc:  # a broken rule should fail loudly, not silently pass
                log.exception("rule %s raised", spec.get("name", spec.get("type")))
                results.append(
                    RuleResult(
                        name=spec.get("name", spec.get("type", "unknown")),
                        rule_type=spec.get("type", "unknown"),
                        column=spec.get("column"),
                        severity="error",
                        passed=False,
                        failed_rows=len(df),
                        total_rows=len(df),
                        detail=f"rule raised {type(exc).__name__}: {exc}",
                    )
                )
        result = GateResult(self.dataset, results)
        for r in result.warnings:
            log.warning("WARN %s: %s failing rows (%s)", r.name, r.failed_rows, r.detail)
        for r in result.blocking_failures:
            log.error("FAIL %s: %s failing rows (%s)", r.name, r.failed_rows, r.detail)
        return result

    def enforce(self, df: pd.DataFrame) -> GateResult:
        """Evaluate and raise QualityGateFailed so the orchestrator halts downstream tasks."""
        result = self.evaluate(df)
        if not result.passed:
            raise QualityGateFailed(result)
        return result
