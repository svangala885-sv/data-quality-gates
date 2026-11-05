"""Declarative data quality gates for batch pipelines."""

from .rules import RuleResult, build_rule
from .gate import GateResult, QualityGate, QualityGateFailed
from .reconcile import reconcile

__all__ = [
    "RuleResult",
    "build_rule",
    "GateResult",
    "QualityGate",
    "QualityGateFailed",
    "reconcile",
]
__version__ = "0.1.0"
