"""Turn a failed gate into a short, human-readable incident summary.

The default summarizer is deterministic and needs no external service. An LLM
can be plugged in through the `llm` callable (for example a wrapper around
Amazon Bedrock or Azure OpenAI); its output is only used as an addition to the
deterministic facts, never as a replacement, so the alert stays trustworthy
when the model is unavailable.
"""

from __future__ import annotations

from typing import Callable

from .gate import GateResult

HINTS = {
    "not_null": "Check for upstream schema changes or a source column that was renamed or dropped.",
    "unique": "Look for a replayed or double-delivered source file, or a join that fans out rows.",
    "in_range": "Compare against the previous load; a unit change (cents vs dollars) is a common cause.",
    "accepted_values": "A new code value may have been introduced upstream; confirm with the source owner.",
    "regex": "Format drift in the source system; check recent releases on the producing application.",
    "row_count": "The extract may be partial; verify the upstream job finished and the file is complete.",
    "freshness": "The source has not delivered new data; check the upstream schedule and connectivity.",
}


def summarize(result: GateResult, llm: Callable[[str], str] | None = None) -> str:
    if result.passed and not result.warnings:
        return f"[{result.dataset}] all {len(result.results)} checks passed."
    lines = [f"[{result.dataset}] quality gate {'FAILED' if not result.passed else 'passed with warnings'}"]
    for r in result.blocking_failures + result.warnings:
        tag = "BLOCKING" if r.severity == "error" else "WARN"
        sample = f" e.g. {r.sample_failures[:3]}" if r.sample_failures else ""
        lines.append(f"- {tag} {r.name}: {r.failed_rows}/{r.total_rows} rows. {r.detail}.{sample}")
        lines.append(f"  Likely cause: {HINTS.get(r.rule_type, 'Investigate the upstream change log.')}")
    text = "\n".join(lines)
    if llm is not None:
        try:
            text += "\n\nModel-generated notes (verify before acting):\n" + llm(text)
        except Exception as exc:  # never let the model break alerting
            text += f"\n\n(LLM summary unavailable: {type(exc).__name__})"
    return text
